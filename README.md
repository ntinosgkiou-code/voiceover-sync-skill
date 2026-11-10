# voiceover-sync: a Claude Code skill

Turn a **voiceover** (ElevenLabs, any TTS or a recorded narration) plus a **silent screen recording** into
one smooth onboarding video in which every click happens on the spoken word.

The audio is never stretched. The video is retimed, cut and crossfaded around it:

- **Click-to-word sync**: each button press lands on its cue ("click **Create** Workspace").
- **No frozen screens**: narration with no matching action (intro, concepts, recap) is covered with real
  footage or slow push-in stills.
- **Cuts instead of fast-forward**: screen-editor zoom-out bounces and detours are removed, and speed stays
  between 0.5× and 2×.
- **Captions** burned into the picture (they show in every player), plus a soft track and an `.srt` for
  YouTube.
- **Chapters**, loudness normalized to −16 LUFS, and H.264 High / yuv420p that plays everywhere.
- **Automatic QA**: codec, length drift, freezes, speed range, loudness, and a contact sheet with one frame
  per cue word.

## Install

```bash
git clone https://github.com/ntinosgkiou-code/voiceover-sync-skill ~/.claude/skills/voiceover-sync
```

```bash
pip install faster-whisper
```

You also need `ffmpeg` and `ffprobe` on PATH (on Windows: `winget install Gyan.FFmpeg`).

## Use

In Claude Code, attach your mp3 and screen recording and say "sync the voice with the recording", or
run `/voiceover-sync`. Claude follows [SKILL.md](SKILL.md):

1. `scripts/make_srt.py` transcribes the voice with word timestamps and writes captions.
2. `scripts/scan.py` maps the recording (scene changes, 1 fps contact sheets, 0.2 s close-ups around
   clicks, crop detection).
3. Claude writes a JSON timeline (see [examples/onboarding-create-new.json](examples/onboarding-create-new.json)).
4. `scripts/sync.py` renders it.
5. `scripts/evaluate.py` scores the render. Claude loops until there are no issues and every cue frame
   matches its word.

### Timeline items

| Item | Meaning |
|---|---|
| `{"clip": [v0, v1], "a": [a0, a1]}` | Source range retimed to fill the audio range. Set v1 = click time and a1 = cue-word time. |
| `{"parts": [[v0,v1],[v0,v1]], "a": [a0,a1]}` | Jump-cut ranges at one shared speed, crossfaded. Use it to drop zoom-outs and pauses. |
| `{"still": t, "a": [a0,a1], "focus": [fx,fy], "zoom": 0.07}` | Slow push-in on one frame, for narration with no matching footage. |

Contiguous joins are hard cuts; all other joins are crossfades that keep the timeline in place.

## Example result

From a 151 s screen recording and a 100.5 s ElevenLabs voiceover, the skill produced a 101 s video with
10/10 clicks on their words (each 0.2–0.4 s after the word starts), no freezes over 1.5 s, speeds
between 0.55× and 1.71×, and −16.4 LUFS.

## License

MIT
