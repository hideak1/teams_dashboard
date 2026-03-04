---
name: team-dashboard
description: >
  Real-time monitoring dashboard for Claude Code agent teams.
  Trigger when the user wants to: start/open/launch the team dashboard,
  view team status, monitor agents, check task progress, see token usage,
  or mentions "team dashboard", "dashboard", "agent monitor",
  "open dashboard", "show teams", "team monitor". Also trigger when the user asks about
  team activity, agent status, or wants a visual overview of their teams.
---

# Team Dashboard

You manage a real-time dashboard server for monitoring Claude Code agent teams.

## Project Location

This skill's root directory is the folder containing this `SKILL.md` file. All commands below use `$PROJECT_DIR` to refer to it. Before running any command, resolve it:
```bash
PROJECT_DIR="$(cd "$(dirname "$(find ~/.claude -name SKILL.md -path '*/teams-dashboard/*' 2>/dev/null | head -1)")" 2>/dev/null && pwd)"
```
If that fails, check `which team-dashboard` or ask the user where they cloned the repo.

## Starting the Dashboard

When the user wants to start/open the dashboard:

1. Check if the server is already running:
   ```bash
   curl -s http://localhost:3741/api/stats >/dev/null 2>&1 && echo "RUNNING" || echo "STOPPED"
   ```

2. If STOPPED, start it:
   ```bash
   cd "$PROJECT_DIR" && source .venv/bin/activate && python -m team_dashboard.server &
   ```
   Wait 2 seconds, then verify with `curl -s http://localhost:3741/api/stats`.

3. Tell the user: **Dashboard is running at http://localhost:3741**

4. If the user wants to open it in a browser:
   ```bash
   open http://localhost:3741
   ```

## Stopping the Dashboard

```bash
pkill -f "team_dashboard.server"
```

## First-Time Setup

If `.venv` doesn't exist or frontend isn't built:
```bash
cd "$PROJECT_DIR"
uv venv .venv && source .venv/bin/activate
uv pip install fastapi uvicorn pydantic websockets
cd frontend && npm install && npm run build
```

Then register hooks for event tracking:
```bash
cd "$PROJECT_DIR"
python3 scripts/register_hooks.py
```
Remind user to restart Claude Code for hooks to take effect.

## Answering Questions About Teams

When the user asks about team status without wanting the full dashboard, you can query the API directly:

- **List teams**: `curl -s http://localhost:3741/api/teams`
- **Team detail**: `curl -s http://localhost:3741/api/teams/{name}`
- **Global stats**: `curl -s http://localhost:3741/api/stats`
- **Agent events**: `curl -s http://localhost:3741/api/agents/{agentId}`

If the server isn't running, start it first, then query.

## Architecture

- **Backend**: FastAPI at port 3741, polls `~/.claude/teams/` and `~/.claude/tasks/` every 2s
- **Frontend**: React + Recharts, pre-built static files served by FastAPI
- **Database**: SQLite at `~/.claude/team-dashboard.db` (WAL mode)
- **Real-time**: WebSocket at `/ws` pushes file changes and hook events to browser
- **Hooks**: 5 hook events (SessionStart/PreToolUse/PostToolUse/Stop/SessionEnd) POST to `/api/events`
- **Token estimation**: `≈ len(text)/4` (English) or `/2` (CJK), always show ≈ prefix

## Pages

1. `/` — Teams Overview: card grid, green=active / gray=ended, filter tabs
2. `/teams/:name` — Team Detail: agent status dots, task kanban, inbox, token bar chart
3. `/agents/:id` — Agent Detail: event timeline, token line chart
4. `/stats` — Global Stats: total tokens, cost estimates (Sonnet/Opus), timeline
