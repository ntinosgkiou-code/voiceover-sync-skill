"""Transcribe a voiceover and write word-timed captions (.srt) plus a words.json.

usage: python -I make_srt.py voice.mp3 out.srt [model=small]
Captions break at sentence ends, pauses > 0.35 s, 42 characters, or 3.2 s.
"""
import json, sys
from faster_whisper import WhisperModel

audio, out = sys.argv[1], sys.argv[2]
model = sys.argv[3] if len(sys.argv) > 3 else "small"
segs, _ = WhisperModel(model, device="cpu", compute_type="int8").transcribe(audio, word_timestamps=True)
words = [(w.start, w.end, w.word.strip()) for s in segs for w in s.words]
json.dump(words, open(out.rsplit(".", 1)[0] + ".words.json", "w", encoding="utf-8"), indent=0)

cues, cur = [], []
for i, (s, e, w) in enumerate(words):
    cur.append((s, e, w))
    text = " ".join(x[2] for x in cur)
    nxt = words[i + 1] if i + 1 < len(words) else None
    gap = (nxt[0] - e) if nxt else 9
    if (w[-1] in ".!?" or gap > 0.35 or len(text) > 42 or e - cur[0][0] > 3.2 or not nxt):
        cues.append((cur[0][0], e, text))
        cur = []

def ts(t):
    ms = int(round(t * 1000))
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"

with open(out, "w", encoding="utf-8") as f:
    for n, (s, e, text) in enumerate(cues, 1):
        nxt_start = cues[n][0] if n < len(cues) else e + 1
        e = min(e + 0.25, nxt_start - 0.02)  # hold each caption slightly past the last word
        f.write(f"{n}\n{ts(s)} --> {ts(e)}\n{text}\n\n")
print(f"{len(cues)} captions -> {out}")
