#!/usr/bin/env python3
"""Ask for a phone number out loud, record the answer, and transcribe it.

Speaks the question with Piper, records a fixed window from the microphone,
transcribes it with faster-whisper, pulls the digits out of the transcript,
and reads them back. Every answer is saved as a .wav plus a row in answers.csv,
so the raw transcripts can be compared later: digit strings are where
transcription makes its characteristic mistakes.

    python ask_phone_number.py
    python ask_phone_number.py --seconds 10 --model tiny.en
"""

import argparse
import csv
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
from piper import PiperVoice

SAMPLE_RATE = 16000
LAB_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VOICE = LAB_DIR / "voices" / "en_GB-alan-medium.onnx"
DEFAULT_OUT = Path(__file__).resolve().parent / "phone_answers"

QUESTION = "Sir, what is your phone number? Please say it after the prompt."

# Whisper writes digits most of the time, but sometimes spells them out.
WORD_DIGITS = {
    "zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2", "three": "3",
    "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}


def extract_digits(text: str) -> str:
    """Turns '607-555-0142' or 'six oh seven, five five five...' into '6075550142'."""
    digits = []
    for token in re.findall(r"[a-z]+|\d", text.lower()):
        if token.isdigit():
            digits.append(token)
        elif token in WORD_DIGITS:
            digits.append(WORD_DIGITS[token])
    return "".join(digits)


def spoken_groups(digits: str) -> str:
    """'6075550142' -> '6 0 7, 5 5 5, 0 1 4 2' so the readback is paced like a person."""
    if len(digits) == 10:
        groups = [digits[:3], digits[3:6], digits[6:]]
    else:
        groups = [digits[i:i + 3] for i in range(0, len(digits), 3)]
    return ", ".join(" ".join(g) for g in groups)


class Speaker:
    """Synthesizes with Piper and plays through the default output device."""

    def __init__(self, voice_path: Path) -> None:
        self.voice = PiperVoice.load(str(voice_path))

    def say(self, text: str) -> None:
        for chunk in self.voice.synthesize(text):
            audio = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16)
            sd.play(audio, samplerate=chunk.sample_rate)
            sd.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="base.en",
                        help="whisper model size (default: base.en)")
    parser.add_argument("--voice", type=Path, default=DEFAULT_VOICE)
    parser.add_argument("--seconds", type=float, default=12.0,
                        help="how long to record the answer (default: 12)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="folder for recordings and answers.csv")
    args = parser.parse_args()

    if not args.voice.is_file():
        sys.exit(f"Piper voice not found at {args.voice}. "
                 f"Run: python3 -m piper.download_voices en_GB-alan-medium "
                 f"--data-dir {LAB_DIR / 'voices'}")

    # Load everything up front so recording starts right after the question.
    print("Loading models...", flush=True)
    recognizer = WhisperModel(args.model, device="cpu", compute_type="int8")
    speaker = Speaker(args.voice)

    speaker.say(QUESTION)
    print(f"Listening for {args.seconds:.0f}s... say your phone number now.", flush=True)
    audio = sd.rec(int(args.seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                   channels=1, dtype="float32")
    sd.wait()
    audio = audio.reshape(-1)

    t0 = time.perf_counter()
    segments, _ = recognizer.transcribe(audio, beam_size=1)
    heard = " ".join(s.text.strip() for s in segments)
    t_asr = time.perf_counter() - t0

    digits = extract_digits(heard)
    print(f"\n  heard:  {heard!r}")
    print(f"  digits: {digits or '(none)'} ({len(digits)} digits)")
    print(f"  [asr {t_asr:.2f}s with {args.model}]")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    args.out.mkdir(parents=True, exist_ok=True)
    wav_path = args.out / f"phone_{stamp}.wav"
    sf.write(wav_path, audio, SAMPLE_RATE)
    csv_path = args.out / "answers.csv"
    new_file = not csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["timestamp", "model", "transcript", "digits", "audio"])
        writer.writerow([stamp, args.model, heard, digits, wav_path.name])
    print(f"  saved:  {wav_path} and {csv_path}")

    if len(digits) == 10:
        speaker.say(f"Thank you, sir. I have {spoken_groups(digits)}.")
    elif digits:
        speaker.say(f"I heard {spoken_groups(digits)}. That is {len(digits)} digits, "
                    f"not ten, sir.")
    else:
        speaker.say("My apologies, sir. I did not catch a number.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
