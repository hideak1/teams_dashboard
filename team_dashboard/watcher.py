"""File system watcher — polls ~/.claude/teams/, ~/.claude/tasks/, and event log every 2 seconds.

Detects:
  - New/updated team configs
  - New/updated task files
  - New/updated inbox messages
  - Team lifecycle (active vs ended)
  - New hook events from JSONL log (persisted by hooks, never lost)

Pushes changes via a callback to the WebSocket broadcaster.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, Optional

from . import db
from .token_estimator import estimate_tokens

logger = logging.getLogger(__name__)

CLAUDE_DIR = Path.home() / ".claude"
TEAMS_DIR = CLAUDE_DIR / "teams"
TASKS_DIR = CLAUDE_DIR / "tasks"
EVENT_LOG = CLAUDE_DIR / "dashboard-events.jsonl"
POLL_INTERVAL = 2.0  # seconds


class FileWatcher:
    def __init__(self, on_change: Optional[Callable] = None):
        self.on_change = on_change
        self._file_mtimes: dict[str, float] = {}
        self._known_teams: set[str] = set()
        self._running = False
        self._event_log_offset: int = 0

    async def start(self):
        self._running = True
        # Initialize offset to current file size so we don't re-ingest on restart
        self._event_log_offset = self._init_event_log_offset()
        logger.info("File watcher started (polling every %.1fs), event log offset=%d", POLL_INTERVAL, self._event_log_offset)
        while self._running:
            try:
                changed = await asyncio.to_thread(self._poll)
                if changed and self.on_change:
                    await self.on_change(changed)
            except Exception:
                logger.exception("Watcher poll error")
            await asyncio.sleep(POLL_INTERVAL)

    def stop(self):
        self._running = False

    def _poll(self) -> list[dict]:
        """Synchronous poll — runs in thread pool."""
        changes: list[dict] = []
        current_teams: set[str] = set()

        # Scan teams directory
        if TEAMS_DIR.is_dir():
            for team_dir in TEAMS_DIR.iterdir():
                if not team_dir.is_dir():
                    continue
                team_name = team_dir.name
                current_teams.add(team_name)

                # Team config
                config_file = team_dir / "config.json"
                if config_file.exists():
                    if self._file_changed(config_file):
                        data = self._read_json(config_file)
                        if data:
                            self._sync_team(team_name, data)
                            changes.append({"type": "team_update", "team": team_name})

                # Inbox messages
                inbox_dir = team_dir / "inboxes"
                if inbox_dir.is_dir():
                    for inbox_file in inbox_dir.glob("*.json"):
                        if self._file_changed(inbox_file):
                            agent_name = inbox_file.stem
                            messages = self._read_json(inbox_file)
                            if isinstance(messages, list):
                                self._sync_inbox(team_name, agent_name, messages)
                                changes.append({"type": "inbox_update", "team": team_name, "agent": agent_name})

        # Scan tasks directory
        if TASKS_DIR.is_dir():
            for task_dir in TASKS_DIR.iterdir():
                if not task_dir.is_dir():
                    continue
                team_name = task_dir.name
                for task_file in task_dir.glob("*.json"):
                    if self._file_changed(task_file):
                        data = self._read_json(task_file)
                        if data:
                            self._sync_task(team_name, data)
                            changes.append({"type": "task_update", "team": team_name, "task_id": data.get("id", "")})

        # Detect ended teams (directory removed)
        ended = self._known_teams - current_teams
        for team_name in ended:
            self._mark_team_inactive(team_name)
            changes.append({"type": "team_ended", "team": team_name})

        self._known_teams = current_teams

        # Ingest new events from JSONL log
        new_events = self._read_event_log()
        for evt in new_events:
            changes.append(evt)

        return changes

    def _file_changed(self, path: Path) -> bool:
        key = str(path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return False
        if key not in self._file_mtimes or self._file_mtimes[key] < mtime:
            self._file_mtimes[key] = mtime
            return True
        return False

    def _read_json(self, path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read %s: %s", path, e)
            return None

    def _sync_team(self, team_name: str, config: dict):
        members = config.get("members", [])
        lead = config.get("leadAgentId", "").split("@")[0] if config.get("leadAgentId") else ""

        # Count tasks
        task_dir = TASKS_DIR / team_name
        task_count = len(list(task_dir.glob("*.json"))) if task_dir.is_dir() else 0

        # Team is active only if at least one member has isActive=true
        has_active_member = any(m.get("isActive", False) for m in members)

        db.upsert_team(
            name=team_name,
            description=config.get("description", ""),
            created_at=config.get("createdAt", 0),
            lead=lead,
            member_count=len(members),
            task_count=task_count,
            active=has_active_member,
            config_json=json.dumps(config),
        )

        # Store lead session mapping if available
        lead_session_id = config.get("leadSessionId", "")
        if lead_session_id:
            lead_name = ""
            lead_cwd = ""
            for m in members:
                if m.get("agentId") == config.get("leadAgentId", ""):
                    lead_name = m.get("name", "")
                    lead_cwd = m.get("cwd", "")
                    break
            if lead_name:
                db.upsert_session_map(
                    session_id=lead_session_id,
                    team_name=team_name,
                    agent_name=lead_name,
                    agent_id=config.get("leadAgentId", ""),
                    cwd=lead_cwd,
                )

        # Sync members and build pane_id → agent mapping
        for member in members:
            agent_type = member.get("agentType", "")
            is_lead = agent_type == "team-lead" or member.get("agentId", "") == config.get("leadAgentId", "")
            status = "lead" if is_lead else "idle"

            db.upsert_agent(
                agent_id=member.get("agentId", ""),
                team_name=team_name,
                name=member.get("name", ""),
                agent_type=agent_type,
                model=member.get("model", ""),
                cwd=member.get("cwd", ""),
                color=member.get("color", ""),
                joined_at=member.get("joinedAt", 0),
                status=status,
            )

            # Register tmux pane → agent mapping for event attribution
            pane_id = member.get("tmuxPaneId", "")
            if pane_id:
                db.upsert_pane_map(
                    pane_id=pane_id,
                    team_name=team_name,
                    agent_name=member.get("name", ""),
                    agent_id=member.get("agentId", ""),
                )

    def _sync_task(self, team_name: str, data: dict):
        db.upsert_task(
            team_name=team_name,
            task_id=data.get("id", ""),
            subject=data.get("subject", ""),
            active_form=data.get("activeForm", ""),
            owner=data.get("owner", ""),
            status=data.get("status", "pending"),
            blocks_json=json.dumps(data.get("blocks", [])),
            blocked_by_json=json.dumps(data.get("blockedBy", [])),
        )

    def _sync_inbox(self, team_name: str, agent_name: str, messages: list):
        for msg in messages:
            db.upsert_inbox_message(
                team_name=team_name,
                agent_name=agent_name,
                from_agent=msg.get("from", ""),
                text=msg.get("text", ""),
                summary=msg.get("summary", ""),
                timestamp=msg.get("timestamp", ""),
                is_read=msg.get("read", False),
            )

    def _mark_team_inactive(self, team_name: str):
        team = db.get_team(team_name)
        if team and team["active"]:
            db.upsert_team(
                name=team_name,
                description=team["description"],
                created_at=team["created_at"],
                lead=team["lead_agent_id"],
                member_count=team["member_count"],
                task_count=team["task_count"],
                active=False,
                config_json=team["config_json"],
            )

    # --- Event log ingestion ---

    def _init_event_log_offset(self) -> int:
        """Get the last ingested offset from DB, or 0 for first run (full ingest)."""
        offset = db.get_meta("event_log_offset")
        if offset is not None:
            return int(offset)
        # First run: skip existing content (already lost before dashboard existed)
        if EVENT_LOG.exists():
            return EVENT_LOG.stat().st_size
        return 0

    def _read_event_log(self) -> list[dict]:
        """Read new lines from the JSONL event log, process each event."""
        if not EVENT_LOG.exists():
            return []

        file_size = EVENT_LOG.stat().st_size
        if file_size <= self._event_log_offset:
            if file_size < self._event_log_offset:
                # File was truncated/rotated, reset
                self._event_log_offset = 0
            else:
                return []

        changes = []
        try:
            with open(EVENT_LOG, "r", encoding="utf-8") as f:
                f.seek(self._event_log_offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                        evt = self._process_event(payload)
                        if evt:
                            changes.append(evt)
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed event log line")
                self._event_log_offset = f.tell()
            db.set_meta("event_log_offset", str(self._event_log_offset))
        except OSError as e:
            logger.warning("Failed to read event log: %s", e)

        return changes

    def _process_event(self, payload: dict) -> Optional[dict]:
        """Process a single hook event payload — same logic as POST /api/events."""
        hook_event = payload.get("hook_event_name", payload.get("hookEventName", "unknown"))
        session_id = payload.get("session_id", payload.get("sessionId", ""))
        tool_name = payload.get("tool_name", payload.get("toolName", ""))
        tmux_pane_id = payload.get("tmux_pane_id", "")

        # Estimate tokens
        tool_input = payload.get("tool_input", payload.get("toolInput", ""))
        tool_result = payload.get("tool_result", payload.get("toolResult", ""))
        input_str = json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input)
        output_str = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
        input_size = len(input_str)
        output_size = len(output_str)
        tokens = estimate_tokens(input_str + output_str)

        # Resolve team/agent
        team_name = payload.get("team_name", payload.get("teamName", ""))
        agent_name = payload.get("agent_name", payload.get("agentName", ""))

        # 1) pane_id mapping
        if tmux_pane_id and (not team_name or not agent_name):
            pane_mapping = db.get_pane_agent(tmux_pane_id)
            if pane_mapping:
                team_name = team_name or pane_mapping["team_name"]
                agent_name = agent_name or pane_mapping["agent_name"]
                if session_id:
                    db.upsert_session_map(
                        session_id=session_id,
                        team_name=team_name,
                        agent_name=agent_name,
                        agent_id=pane_mapping.get("agent_id", ""),
                    )

        # 2) session_map
        if session_id and (not team_name or not agent_name):
            mapping = db.get_session_agent(session_id)
            if mapping:
                team_name = team_name or mapping["team_name"]
                agent_name = agent_name or mapping["agent_name"]

        # 3) cwd match on SessionStart
        if hook_event == "SessionStart" and session_id:
            cwd = payload.get("cwd", "")
            if cwd and (not team_name or not agent_name):
                matched = db.match_session_to_agent(cwd)
                if matched:
                    team_name = team_name or matched["team_name"]
                    agent_name = agent_name or matched["name"]
                    db.upsert_session_map(
                        session_id=session_id,
                        team_name=team_name,
                        agent_name=agent_name,
                        agent_id=matched.get("agent_id", ""),
                        cwd=cwd,
                    )
            elif team_name and agent_name:
                db.upsert_session_map(
                    session_id=session_id,
                    team_name=team_name,
                    agent_name=agent_name,
                    cwd=payload.get("cwd", ""),
                )

        db.insert_event(
            session_id=session_id,
            team_name=team_name,
            agent_name=agent_name,
            hook_event=hook_event,
            tool_name=tool_name,
            input_size=input_size,
            output_size=output_size,
            estimated_tokens=tokens,
            payload_json=json.dumps(payload, default=str)[:10000],
        )

        # Update agent token count
        if agent_name and team_name:
            agent_id = f"{agent_name}@{team_name}"
            db.add_agent_tokens(agent_id, tokens)

        return {
            "type": "event",
            "hook_event": hook_event,
            "team": team_name,
            "agent": agent_name,
            "tool": tool_name,
            "tokens": tokens,
        }
