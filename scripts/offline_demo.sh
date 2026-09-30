#!/bin/bash
# Offline demonstration. Turn Wi-Fi OFF first, then run:   ./scripts/offline_demo.sh
# Everything printed here is also saved to evidence/offline/transcript.txt
set -u
cd "$(dirname "$0")/.."
OUT=evidence/offline
mkdir -p "$OUT"
LOG="$OUT/transcript.txt"
: > "$LOG"

run() {                      # print the command, run it, time it, keep the output
  echo "" | tee -a "$LOG"
  echo "\$ $*" | tee -a "$LOG"
  local t0=$(date +%s)
  "$@" 2>&1 | tee -a "$LOG"
  echo "[took $(( $(date +%s) - t0 ))s]" | tee -a "$LOG"
}

echo "=== Offline demo · $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG"

# 0. Prove the machine is offline ------------------------------------------------------
run networksetup -getairportpower en0
run sh -c 'route -n get default 2>&1 | head -3 || true'
run sh -c 'curl -s -m 5 -o /dev/null -w "%{http_code}\n" https://www.google.com || echo "curl: no internet (expected)"'
NET=$(python3 -c 'import sys; sys.path.insert(0, "."); from wikicli.env import network_status; print(network_status())')
echo "network check: $NET" | tee -a "$LOG"
if [ "$NET" != "offline" ] && [ "${ALLOW_ONLINE:-0}" != "1" ]; then
  echo "Still online. Turn Wi-Fi off (and unplug Ethernet), then run this again." | tee -a "$LOG"
  exit 1
fi

# 1. Restart the local runtime so the model is loaded from disk with no network ----------
run brew services restart ollama
sleep 4
run ./wiki --help
run ./wiki status

# 2. Ingestion ---------------------------------------------------------------------------
# a) the real vault: unchanged sources are detected, no duplicate notes
run ./wiki ingest vault/raw
# b) Gemma ingestion of a real source, offline. Done on a throwaway copy so the reviewed
#    notes in the submitted vault are not overwritten; the file list must stay identical.
DEMO=$(mktemp -d)
cp -R wiki wikicli prompts config.json vault "$DEMO/"
ls -R "$DEMO/vault/wiki" > "$DEMO/before.txt"
run "$DEMO/wiki" ingest "$DEMO/vault/raw/IBD Client Questionnaire.docx" --force --overwrite-reviewed
run sh -c "ls -R '$DEMO/vault/wiki' | diff '$DEMO/before.txt' - && echo 'same note files: no duplicates'"
run "$DEMO/wiki" lint
rm -rf "$DEMO"
run ./wiki lint

# 3. Search mode: original passages, no model -------------------------------------------
run ./wiki search "team goals success"

# 4. The four ask-mode tests -> evidence/ask-tests/*.md -----------------------------------
run ./wiki eval

# 5. Chat mode checks (capabilities, draft, follow-up, a claim made only in chat) ---------
run ./wiki chat --script evals/chat_checks.txt
# 6. The chat-only claim must not change ask
run ./wiki ask "When is the IBD application deadline?"

# 7. Memory in use ------------------------------------------------------------------------
run ./wiki status
run sh -c "ps -axo rss=,command= | grep -i '[o]llama' | awk '{printf \"%.2f GB  %s %s %s\n\", \$1/1048576, \$2, \$3, \$4}'"

cp "$(ls -t runs/chat/*.md | head -1)" "evidence/mode-checks/chat-offline.md"
cp "$(ls -t runs/search/*.md | head -1)" "evidence/mode-checks/search-offline.md"
echo "" | tee -a "$LOG"
echo "=== done · transcript: $LOG · evidence cards: evidence/ask-tests/ · mode checks: evidence/mode-checks/" | tee -a "$LOG"
