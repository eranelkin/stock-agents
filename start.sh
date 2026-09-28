#!/usr/bin/env bash
# Starts the backend, AI service, and frontend, each in its own Terminal.app tab.
# Requires PostgreSQL to already be running (docker compose up postgres -d).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

open_tab() {
    local title="$1"
    local cmd="$2"
    osascript <<OSA
tell application "Terminal"
    activate
    tell application "System Events" to keystroke "t" using command down
    delay 0.3
    do script "$cmd" in front window
    set custom title of front window to "$title"
end tell
OSA
}

open_tab "Backend"    "cd '$DIR' && source .venv/bin/activate && uvicorn backend.main:app --port 4101 --reload"
open_tab "AI Service" "cd '$DIR' && source .venv/bin/activate && uvicorn ai_service.main:app --port 4102 --reload"
open_tab "Frontend"   "cd '$DIR/frontend' && npm run dev"

echo "Opened 3 Terminal tabs: Backend (4101), AI Service (4102), Frontend (4100)."
