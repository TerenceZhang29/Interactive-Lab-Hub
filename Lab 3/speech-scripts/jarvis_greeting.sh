#!/usr/bin/env bash
# JARVIS-style greeting with Piper neural TTS (British male voice "alan").
#
# Usage (with the Lab 3 venv active):
#   ./jarvis_greeting.sh            # greets "sir"
#   ./jarvis_greeting.sh "Mr. Stark"

set -euo pipefail
VOICES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/voices"
VOICE="en_GB-alan-medium"
NAME="${1:-sir}"

# Fetch the voice on first run.
if [[ ! -f "$VOICES_DIR/$VOICE.onnx" ]]; then
  python3 -m piper.download_voices "$VOICE" --data-dir "$VOICES_DIR"
fi

HOUR=$(date +%H)
if   (( 10#$HOUR < 12 )); then PART="morning"
elif (( 10#$HOUR < 18 )); then PART="afternoon"
else                           PART="evening"
fi

TEXT="Good $PART, $NAME. All systems are online. How may I assist you today?"

# Stream straight to the speaker so speech starts before synthesis finishes.
python3 -m piper \
  --model "$VOICE" \
  --data-dir "$VOICES_DIR" \
  --output-raw \
  -- "$TEXT" \
  | aplay -q -r 22050 -f S16_LE -t raw -
