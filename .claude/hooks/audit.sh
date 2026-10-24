#!/bin/bash
# Appends one redacted line per tool call: time, tool, sha256 of the input. Never the input itself.
input=$(cat)
dir="${CLAUDE_PROJECT_DIR:-.}/logs"; mkdir -p "$dir"
printf '%s' "$input" | /usr/bin/python3 -c '
import json,sys,hashlib,datetime
d=json.load(sys.stdin)
print(json.dumps({"ts":datetime.datetime.now().astimezone().isoformat(),"tool":d.get("tool_name"),
 "input_sha256":hashlib.sha256(json.dumps(d.get("tool_input",{}),sort_keys=True).encode()).hexdigest()}))' >> "$dir/audit.jsonl"
exit 0
