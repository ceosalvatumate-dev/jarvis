#!/bin/bash
# Blocks destructive or credential-touching tool calls. Exit 0 = no decision.
input=$(cat)
cmd=$(printf '%s' "$input" | /usr/bin/python3 -c 'import json,sys;d=json.load(sys.stdin);t=d.get("tool_input",{});print(t.get("command") or t.get("file_path") or "")')
case "$cmd" in
  *"rm -rf"*|*"git push --force"*|*"| sh"*|*"| bash"*|*"mkfs"*|*".ssh/"*|*".aws/"*|*"channels/"*".env"*|*"/.env"*|*"setup-token"*|*"launchctl unload"*|*"access.json"*|*"meta-sync.py"*)
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Blocked by Jarvis guard (SECURITY.md)"}}'
    exit 0 ;;
esac
exit 0
