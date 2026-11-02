#!/usr/bin/env bash
# Trigger eval: does a fresh Claude Code session load velma-detect-skill for each prompt?
#
# Installs the skill into a temp project under .claude/skills/, runs each prompt in
# evals/trigger_prompts.json with `claude -p`, and checks whether the session called the
# Skill tool for velma-detect-skill. Prints PASS or FAIL per prompt and a summary.
# Exit code 0 if all pass, 1 if any fail, 2 if the eval cannot run.
#
# Needs: claude (Claude Code CLI, logged in), jq. No VELMA_API_KEY is needed or passed:
# the check only looks at whether the skill is loaded, not at the API.
# If ANTHROPIC_API_KEY is set and has no credit, run: env -u ANTHROPIC_API_KEY ./evals/run_trigger_eval.sh

set -u
here="$(cd "$(dirname "$0")/.." && pwd)"
prompts="$here/evals/trigger_prompts.json"
skill_name="velma-detect-skill"

if ! command -v claude >/dev/null 2>&1; then
  echo "NOT RUN: the claude CLI is not installed or not on PATH. Install Claude Code and re-run." >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "NOT RUN: jq is required to read $prompts." >&2
  exit 2
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/.claude/skills/$skill_name"
for item in SKILL.md references scripts LICENSE; do
  [ -e "$here/$item" ] && cp -R "$here/$item" "$tmp/.claude/skills/$skill_name/"
done

pass=0; fail=0
count="$(jq 'length' "$prompts")"
for i in $(seq 0 $((count - 1))); do
  id="$(jq -r ".[$i].id" "$prompts")"
  want="$(jq -r ".[$i].should_trigger" "$prompts")"
  prompt="$(jq -r ".[$i].prompt" "$prompts")"

  # One turn is enough: the Skill tool call happens in the first assistant message.
  loaded="$(cd "$tmp" && env -u VELMA_API_KEY claude -p "$prompt" --output-format stream-json --verbose --max-turns 1 2>/dev/null \
    | jq -R -r 'fromjson? | select(.type == "assistant") | .message.content[]? | select(.type == "tool_use" and .name == "Skill") | .input.skill' \
    | grep -c "^$skill_name$")"
  got=false; [ "${loaded:-0}" -gt 0 ] && got=true

  if [ "$got" = "$want" ]; then
    pass=$((pass + 1)); echo "PASS  #$id  want=$want got=$got"
  else
    fail=$((fail + 1)); echo "FAIL  #$id  want=$want got=$got  prompt: $prompt"
  fi
done

echo "Result: $pass passed, $fail failed, $count total"
[ "$fail" -eq 0 ]
