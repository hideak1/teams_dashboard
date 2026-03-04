"""FastAPI server — REST API + WebSocket + static file serving.

Endpoints:
  GET  /api/teams                   — all teams overview
  GET  /api/teams/{name}            — team detail
  GET  /api/teams/{name}/agents     — agents in team
  GET  /api/teams/{name}/tasks      — tasks for team
  GET  /api/teams/{name}/inbox      — inbox messages
  GET  /api/teams/{name}/tokens     — per-agent token stats
  GET  /api/agents/{agent_id}       — agent detail with events
  GET  /api/events                  — recent events (query params: team, agent, limit)
  GET  /api/stats                   — global statistics
  GET  /api/tokens/timeline         — token usage timeline
  POST /api/events                  — hook event receiver
  WS   /ws                          — real-time updates

Static files served from frontend/dist/ at root.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .token_estimator import estimate_tokens, estimate_cost
from .watcher import FileWatcher

logger = logging.getLogger(__name__)

# --- WebSocket manager ---


class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, data: dict):
        msg = json.dumps(data)
        dead = []
        for ws in self.connections:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
watcher: FileWatcher | None = None


async def on_file_change(changes: list[dict]):
    """Called by watcher when files change — broadcast to all WS clients."""
    for change in changes:
        await manager.broadcast(change)


# --- App lifecycle ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    global watcher
    db.init_db()
    watcher = FileWatcher(on_change=on_file_change)
    task = asyncio.create_task(watcher.start())
    logger.info("Team Dashboard running at http://localhost:3741")
    yield
    watcher.stop()
    task.cancel()


app = FastAPI(title="Team Dashboard", lifespan=lifespan)


# --- Hook event receiver ---


@app.post("/api/events")
async def receive_event(request: Request):
    """Receive hook events from Claude Code."""
    try:
        payload = await request.json()
    except Exception:
        body = await request.body()
        try:
            payload = json.loads(body)
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid JSON"}, status_code=400)

    hook_event = payload.get("hook_event_name", payload.get("hookEventName", "unknown"))
    session_id = payload.get("session_id", payload.get("sessionId", ""))
    tool_name = payload.get("tool_name", payload.get("toolName", ""))

    # Estimate tokens from input + output
    tool_input = payload.get("tool_input", payload.get("toolInput", ""))
    tool_result = payload.get("tool_result", payload.get("toolResult", ""))
    input_str = json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input)
    output_str = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
    input_size = len(input_str)
    output_size = len(output_str)
    tokens = estimate_tokens(input_str + output_str)

    # Try to identify team/agent from session or payload
    team_name = payload.get("team_name", payload.get("teamName", ""))
    agent_name = payload.get("agent_name", payload.get("agentName", ""))
    tmux_pane_id = payload.get("tmux_pane_id", "")

    # Resolution priority: 1) payload fields, 2) pane_id map, 3) session_map, 4) cwd match

    # Pane-based resolution: most reliable for teammate agents
    if tmux_pane_id and (not team_name or not agent_name):
        pane_mapping = db.get_pane_agent(tmux_pane_id)
        if pane_mapping:
            if not team_name:
                team_name = pane_mapping["team_name"]
            if not agent_name:
                agent_name = pane_mapping["agent_name"]
            # Also store in session_map for future lookups without pane_id
            if session_id:
                db.upsert_session_map(
                    session_id=session_id,
                    team_name=team_name,
                    agent_name=agent_name,
                    agent_id=pane_mapping.get("agent_id", ""),
                )

    # Session-based resolution: if team/agent missing, look up session_map
    if session_id and (not team_name or not agent_name):
        mapping = db.get_session_agent(session_id)
        if mapping:
            if not team_name:
                team_name = mapping["team_name"]
            if not agent_name:
                agent_name = mapping["agent_name"]

    # On SessionStart, try to match by cwd and store mapping (fallback)
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
                cwd=cwd,
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
        payload_json=json.dumps(payload, default=str)[:10000],  # cap payload size
    )

    # Update agent token count
    if agent_name and team_name:
        agent_id = f"{agent_name}@{team_name}"
        db.add_agent_tokens(agent_id, tokens)

    # Broadcast to WebSocket clients
    await manager.broadcast({
        "type": "event",
        "hook_event": hook_event,
        "team": team_name,
        "agent": agent_name,
        "tool": tool_name,
        "tokens": tokens,
    })

    return {"ok": True}


# --- REST API ---


@app.get("/api/teams")
async def list_teams(filter: str = "all"):
    teams = db.get_all_teams()
    if filter == "active":
        teams = [t for t in teams if t["active"]]
    elif filter == "ended":
        teams = [t for t in teams if not t["active"]]
    return teams


@app.get("/api/teams/{name}")
async def get_team(name: str):
    team = db.get_team(name)
    if not team:
        return JSONResponse({"error": "team not found"}, status_code=404)
    agents = db.get_agents_for_team(name)
    tasks = db.get_tasks_for_team(name)
    messages = db.get_inbox_for_team(name)
    token_stats = db.get_token_stats(name)
    return {
        **team,
        "agents": agents,
        "tasks": tasks,
        "messages": messages,
        "token_stats": token_stats,
    }


@app.get("/api/teams/{name}/agents")
async def get_team_agents(name: str):
    return db.get_agents_for_team(name)


@app.get("/api/teams/{name}/tasks")
async def get_team_tasks(name: str):
    return db.get_tasks_for_team(name)


@app.get("/api/teams/{name}/inbox")
async def get_team_inbox(name: str, limit: int = 50):
    return db.get_inbox_for_team(name, limit)


@app.get("/api/teams/{name}/tokens")
async def get_team_tokens(name: str):
    return db.get_token_stats(name)


@app.get("/api/agents/{agent_id:path}")
async def get_agent(agent_id: str):
    conn = db.get_conn()
    agent = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
    conn.close()
    if not agent:
        return JSONResponse({"error": "agent not found"}, status_code=404)
    agent_dict = dict(agent)
    events = db.get_events(agent_name=agent_dict["name"], limit=200)
    tasks = db.get_tasks_for_agent(agent_dict["team_name"], agent_dict["name"])
    messages = db.get_inbox_for_agent(agent_dict["team_name"], agent_dict["name"])
    return {"agent": agent_dict, "events": events, "tasks": tasks, "messages": messages}


@app.get("/api/events")
async def list_events(team: str = "", agent: str = "", limit: int = 100):
    return db.get_events(team_name=team, agent_name=agent, limit=limit)


@app.get("/api/stats")
async def global_stats():
    stats = db.get_global_stats()
    total_tokens = stats["total_estimated_tokens"]
    stats["estimated_cost_sonnet"] = round(estimate_cost(total_tokens, "sonnet"), 4)
    stats["estimated_cost_opus"] = round(estimate_cost(total_tokens, "opus"), 4)
    return stats


@app.get("/api/tokens/timeline")
async def token_timeline(team: str = "", agent: str = "", bucket: int = 60):
    return db.get_token_timeline(team_name=team, agent_name=agent, bucket_seconds=bucket)


# --- WebSocket ---


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        manager.disconnect(ws)


# --- Static files (React frontend) ---

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@app.get("/{path:path}")
async def serve_frontend(path: str):
    """Serve React SPA — try exact file, fall back to index.html."""
    if not FRONTEND_DIR.exists():
        return JSONResponse({"error": "frontend not built, run: cd frontend && npm run build"}, status_code=503)
    file_path = FRONTEND_DIR / path
    if file_path.is_file():
        return FileResponse(file_path)
    index = FRONTEND_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return JSONResponse({"error": "not found"}, status_code=404)


# --- CLI entry point ---


def main():
    import uvicorn

    port = int(os.environ.get("DASHBOARD_PORT", "3741"))
    log_level = os.environ.get("DASHBOARD_LOG_LEVEL", "info")
    uvicorn.run(
        "team_dashboard.server:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        reload=False,
    )


if __name__ == "__main__":
    main()
