#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

open_terminal() {
    local title="$1"
    local cmd="$2"
    osascript \
        -e 'tell application "Terminal"' \
        -e "  do script \"echo -ne '\\\\033]0;${title}\\\\007'; ${cmd}\"" \
        -e '  activate' \
        -e 'end tell'
}

open_terminal "backend (4101)"    "cd '$ROOT' && uvicorn backend.main:app --port 4101 --reload"
open_terminal "ai-service (4102)" "cd '$ROOT' && uvicorn ai_service.main:app --port 4102 --reload"
open_terminal "frontend (5173)"   "cd '$ROOT/frontend' && npm run dev"
