# Team Dashboard

Real-time monitoring dashboard for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) agent teams.

When you use Claude Code's team/swarm features to coordinate multiple agents, this dashboard gives you a live bird's-eye view of everything that's happening — agent status, task progress, token usage, and inter-agent messages.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![React](https://img.shields.io/badge/React-18-61dafb?logo=react)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Teams Overview** — Card grid showing all active & ended teams at a glance
- **Live Agent Status** — See which agents are working, idle, or stopped in real-time
- **Task Kanban Board** — 3-column board (Pending / In Progress / Completed) per team
- **Token Usage Tracking** — Per-agent token estimates with cost breakdown (Sonnet / Opus)
- **Agent Timeline** — Full event history per agent (tool calls, session events)
- **Inbox Monitor** — View inter-agent messages and broadcasts
- **WebSocket Push** — Instant UI updates, no manual refresh needed
- **Dark Theme** — Easy on the eyes during long coding sessions

## Demo
![Kapture 2026-03-04 at 01 01 47](https://github.com/user-attachments/assets/71173130-65ac-4b69-b509-4054f7b02e9e)


## How It Works

```
Claude Code Agents
    │
    ├── Hook Events (SessionStart/PreToolUse/PostToolUse/Stop/SessionEnd)
    │   └── Appended to ~/.claude/dashboard-events.jsonl
    │
    ├── Team configs   → ~/.claude/teams/{team-name}/config.json
    └── Task files     → ~/.claude/tasks/{team-name}/

         ▼ polled every 2s

  ┌─────────────────────────────────┐
  │  FastAPI Server (port 3741)     │
  │  ├── REST API  /api/*           │
  │  ├── WebSocket /ws              │
  │  └── SQLite DB (WAL mode)       │
  └──────────┬──────────────────────┘
             │ serves static files
             ▼
  ┌─────────────────────────────────┐
  │  React SPA (Vite build)         │
  │  ├── Teams Overview    /        │
  │  ├── Team Detail       /teams/* │
  │  ├── Agent Detail      /agents/*│
  │  └── Global Stats      /stats   │
  └─────────────────────────────────┘
```

## Prerequisites

- **Python 3.9+** (with [uv](https://docs.astral.sh/uv/) recommended, pip works too)
- **Node.js 18+** (npm or [Bun](https://bun.sh))
- **Claude Code** installed and configured

## Installation

### One-Click Install

```bash
git clone https://github.com/YOUR_USERNAME/teams-dashboard.git
cd teams-dashboard
bash scripts/install.sh
```

This will:
1. Create a Python virtual environment and install dependencies
2. Build the React frontend
3. Register Claude Code hooks for event tracking

> **Note:** Restart Claude Code after installation for hooks to take effect.

### Manual Install

```bash
# 1. Python backend
uv venv .venv && source .venv/bin/activate
uv pip install fastapi uvicorn pydantic websockets

# 2. Frontend
cd frontend
npm install
npm run build
cd ..

# 3. Register hooks
python3 scripts/register_hooks.py
```

## Usage

### Start the Dashboard

```bash
cd teams-dashboard
source .venv/bin/activate
python -m team_dashboard.server
```

Then open **http://localhost:3741** in your browser.

### Use as a Claude Code Skill

Copy the `SKILL.md` file to your Claude Code skills directory. Then just tell Claude:

> "Open the team dashboard" / "Show me team status" / "Launch agent monitor"

Claude will automatically start the server and open the dashboard for you.

### Stop the Dashboard

```bash
pkill -f "team_dashboard.server"
```

### Check if Running

```bash
curl -s http://localhost:3741/api/stats
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/teams` | List all teams (filter: `all`/`active`/`ended`) |
| `GET` | `/api/teams/{name}` | Team detail with agents, tasks, messages |
| `GET` | `/api/teams/{name}/agents` | List agents in a team |
| `GET` | `/api/teams/{name}/tasks` | List tasks for a team |
| `GET` | `/api/teams/{name}/inbox` | Inter-agent messages |
| `GET` | `/api/teams/{name}/tokens` | Per-agent token statistics |
| `GET` | `/api/agents/{id}` | Agent detail with event timeline |
| `GET` | `/api/events` | Recent events (query: `team`, `agent`, `limit`) |
| `GET` | `/api/stats` | Global statistics & cost estimates |
| `GET` | `/api/tokens/timeline` | Token usage over time |
| `POST` | `/api/events` | Receive hook events from Claude Code |
| `WS` | `/ws` | WebSocket for real-time updates |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, Uvicorn, SQLite (WAL) |
| Frontend | React 18, React Router 6, Recharts, Vite |
| Real-time | WebSocket + file polling (2s interval) |
| Data | SQLite at `~/.claude/team-dashboard.db` |
| Hooks | Claude Code hook events → JSONL log → DB |

## Project Structure

```
teams-dashboard/
├── SKILL.md                  # Claude Code skill definition
├── scripts/
│   ├── install.sh            # One-click installer
│   └── register_hooks.py     # Hook registration script
├── team_dashboard/           # Python backend
│   ├── server.py             # FastAPI server (REST + WebSocket)
│   ├── db.py                 # SQLite database layer
│   ├── models.py             # Pydantic models
│   ├── watcher.py            # File watcher for teams/tasks
│   └── token_estimator.py    # Token counting estimates
└── frontend/                 # React frontend
    ├── src/
    │   ├── main.jsx          # App entry point & router
    │   ├── hooks.js          # Custom React hooks
    │   ├── style.css         # Dark theme styles
    │   └── pages/
    │       ├── TeamsOverview.jsx
    │       ├── TeamDetail.jsx
    │       ├── AgentDetail.jsx
    │       └── GlobalStats.jsx
    ├── package.json
    └── vite.config.js
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DASHBOARD_PORT` | `3741` | Server port |
| `DASHBOARD_LOG_LEVEL` | `info` | Logging level |

## Contributing

Contributions are welcome! Feel free to open issues and pull requests.

## License

MIT
