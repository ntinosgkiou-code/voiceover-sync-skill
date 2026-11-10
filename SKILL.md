---
name: voiceover-sync
description: Sync a voiceover (ElevenLabs/TTS/narration mp3) to a silent screen recording so every on-screen click lands on the spoken word, producing one smooth onboarding/tutorial video. Retimes, cuts, and crossfades the footage around the fixed audio, adds captions, chapters and normalized loudness, and checks the result automatically. Use when the user says "/voiceover-sync", "sync the voice with the recording", "συγχρόνισε τη φωνή με το βίντεο", "make an onboarding video from this recording and voiceover", or attaches an mp3 plus a screen recording.
---

# Voiceover ↔ screen recording sync

The **audio is fixed**: never stretch the voice. The video is cut, sped up or slowed down, and
crossfaded so that each action happens on its cue word.

Requirements: `ffmpeg`/`ffprobe` on PATH, Python with `faster-whisper` (`pip install faster-whisper`).
Scripts are in `~/.claude/skills/voiceover-sync/scripts/`. Run Python with `-I`. Use a **short** working folder (for example `work/` in the project). Windows
fails on very long paths such as the deep scratchpad path. Put the deliverable where the user wants it.

## 1. Transcribe the voice (word timestamps)
```
python -I scripts/make_srt.py voice.mp3 work/captions.srt
```
This writes `captions.srt` (short, word-timed lines) and `captions.words.json` (every word with its
start time). The cue words are the verbs: "click", "choose", "open", "name it", "Create X".

## 2. Map the recording
```
python -I scripts/scan.py rec.mp4 work/scan
```
Read the `frame_*.png` first. If the recording shows an **editor around the real content** (Screen
Studio, Clipchamp or OBS preview with toolbars and playback controls), choose a crop box for the inner
preview and re-run the scan with `--crop W:H:X:Y`. Then read the contact sheets (sheet N, index i = second
36·(N−1)+i) and write down each action: dialog opens, option highlighted, name typed, button clicked, page
loads. For each click, pin the exact time with `--fine START END` (0.2 s steps). Look for the frame where
the hand cursor is on the button; the next scene change is when the page reacts.

Also mark:
- **Zoom-out bounces** (the editor's auto-zoom pulls back to a small, blurry dialog). Cut these out
  rather than fast-forwarding through them.
- **Detours** the narration never mentions (opening other pages). Cut them.
- **Full-window shots** and **final states** (e.g. the dashboard at the end). Use them for narration
  that has no matching action (intro, concepts, recap).
- **A recording that ends early**: playback stops while the narration continues, which leaves a long
  static tail.

## 3. Write the timeline config
Copy `examples/onboarding-create-new.json`. Items, with audio times in seconds:
- `{"clip": [v0, v1], "a": [a0, a1]}`: the source range is retimed to fill a0..a1. Choose v1 = click time
  and a1 = cue-word time, so the click lands on the word.
- `{"parts": [[v0,v1],[v0,v1]], "a": [a0,a1]}`: jump-cut ranges at one shared speed, crossfaded. Use it to
  drop zoom-outs and typing pauses.
- `{"still": t, "a": [a0,a1], "focus": [fx,fy], "zoom": 0.07}`: a slow push-in on one frame. Use it for
  intro, concepts or recap when there is no footage; aim `focus` at the part of the screen the voice
  talks about.

Joins between contiguous sources are invisible hard cuts; every other join gets a crossfade that keeps
the timeline in place. The last item should end about 0.5 s after the audio ends. Also fill in `cues`
(audio time plus label for each click word) so you can verify them, and `chapters`.

Rules learned the hard way:
- **Never hold a frame longer than ~2 s.** Users call it "the screen froze". Use real footage or a
  push-in still.
- Prefer **full-window shots** for overview narration. Zoomed shots read as "not the whole screen".
- Keep speed between **0.5× and 2×**. Faster than that through zoom transitions looks jittery and blurred.
  Cut instead.
- Concept narration ("a workflow is a canvas…") is best illustrated by **showing that thing** using
  footage from later in the recording.

## 4. Render and evaluate (loop)
```
python -I scripts/sync.py work/config.json
python -I scripts/evaluate.py work/config.json
```
`evaluate.py` reports the codec (must be H.264 High yuv420p; 4:4:4 does not play on Windows), length
drift, freezes over 1.5 s, speed range, loudness (target −16 LUFS), and writes `<out>.cues.jpg` with one
frame per cue word. **Read the cue sheet**: each frame must show the action the label names (cursor on
the button, option highlighted). Fix the anchors, re-render, and re-evaluate until ISSUES is "none" and
every cue matches. Keep each version (`v3.mp4`, `v4.mp4`, …) and log what changed.

## 5. Deliver
- Save to where the user asked (often `~/Downloads`). Never overwrite a version they approved without
  saying so.
- Captions are **burned into the picture** by default (`"burn_captions": true`), because Windows Media
  Player and Photos never show soft subtitle tracks. The file also keeps a soft track, chapters and the
  `.srt` (for YouTube upload). Set `"burn_captions": false` for a clean version, and change the look
  with `"caption_style"` (ASS force_style).
- Report any mismatches you cannot fix in editing, such as the voice naming something different from what
  is typed on screen, or typos visible in the UI.
- For the sharpest result, the source should be the screen editor's **own export**, not a screen recording
  of its preview. Offer to re-sync from that export, since the same config works with a scale factor.

## Known pitfalls (Windows ffmpeg build)
- `drawtext` with no fontconfig can crash. Use the `subtitles` filter with `fontsdir='C\:/Windows/Fonts'`
  (sync.py does this) instead.
- `xfade` needs matching timebases. `sync.py` sets `settb=1/fps` on every branch.
- Always pass `-pix_fmt yuv420p -profile:v high`. `zoompan`/`unsharp` chains can otherwise produce
  yuv444.
