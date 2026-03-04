"""Register HTTP hooks in ~/.claude/settings.json.

Safely merges dashboard hooks without overwriting existing hook config.
All hooks use async: true so dashboard outages don't affect Claude Code.

The hooks POST stdin JSON to http://localhost:3741/api/events via curl.
"""

import json
import sys
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
DASHBOARD_URL = "http://localhost:3741/api/events"

# Hook events to register
HOOK_EVENTS = ["SessionStart", "PreToolUse", "PostToolUse", "Stop", "SessionEnd"]

# Each hook: read stdin, inject tmux pane ID, append to JSONL log (never lost)
EVENT_LOG = "~/.claude/dashboard-events.jsonl"
HOOK_COMMAND = (
    f'INPUT=$(cat); '
    f'PANE_ID=$(tmux display-message -p "#{{pane_id}}" 2>/dev/null || echo ""); '
    f'PAYLOAD=$(echo "$INPUT" | python3 -c "'
    f'import sys,json; d=json.load(sys.stdin); '
    f'd[\"tmux_pane_id\"]=sys.argv[1]; print(json.dumps(d))" "$PANE_ID" 2>/dev/null || echo "$INPUT"); '
    f'echo "$PAYLOAD" >> {EVENT_LOG}'
)

DASHBOARD_HOOK = {
    "matcher": "*",
    "hooks": [
        {
            "type": "command",
            "command": HOOK_COMMAND,
            "timeout": 5,
        }
    ],
}


def register():
    # Read existing settings
    if SETTINGS_PATH.exists():
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})

    changed = False
    for event in HOOK_EVENTS:
        event_hooks = hooks.setdefault(event, [])
        # Check if our hook is already registered
        already = any(
            DASHBOARD_URL in str(h.get("hooks", [{}])[0].get("command", ""))
            for h in event_hooks
            if isinstance(h, dict)
        )
        if not already:
            event_hooks.append(DASHBOARD_HOOK)
            changed = True
            print(f"  + Registered {event} hook")
        else:
            print(f"  = {event} hook already registered")

    if changed:
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("\nHooks saved to", SETTINGS_PATH)
        print("NOTE: Restart Claude Code for hooks to take effect.")
    else:
        print("\nAll hooks already registered. No changes needed.")


if __name__ == "__main__":
    register()
