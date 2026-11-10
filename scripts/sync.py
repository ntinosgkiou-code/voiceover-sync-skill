"""Sync a silent screen recording to a voiceover from a JSON timeline.

usage: python sync.py config.json

Timeline items (audio times in seconds, "a": [start, end]):
  {"clip":  [v0, v1], "a": [a0, a1]}                  source range retimed to fill a0..a1
  {"parts": [[v0, v1], [v0, v1]], "a": [a0, a1]}      jump-cut ranges sharing one speed
  {"still": t, "a": [a0, a1], "focus": [fx, fy], "zoom": 0.07}   slow push-in on one frame
Adjacent items whose source is contiguous are joined with a hard cut (invisible);
every other join gets a crossfade that does not shift the timeline.
"""
import json, os, subprocess, sys

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
V, A, OUT = cfg["video"], cfg["audio"], cfg["out"]
CROP = f"crop={cfg['crop']}," if cfg.get("crop") else ""
W, H = cfg.get("size", [1920, 1054])
FPS, XF = cfg.get("fps", 30), cfg.get("xfade", 0.35)
SHARP = cfg.get("sharpen", 0.7)
LOOK = f"scale={W}:{H}:flags=lanczos,unsharp=5:5:{SHARP}:5:5:0.0,fps={FPS},setsar=1,format=yuv420p"

# expand "parts" into clips with the same speed, splitting the audio range proportionally
items = []
for it in cfg["timeline"]:
    if "parts" in it:
        a0, a1 = it["a"]
        src = sum(v1 - v0 for v0, v1 in it["parts"])
        k = (a1 - a0) / src
        t = a0
        for v0, v1 in it["parts"]:
            items.append({"clip": [v0, v1], "a": [t, t + (v1 - v0) * k]})
            t += (v1 - v0) * k
    else:
        items.append(dict(it))

def contiguous(p, n):
    return "clip" in p and "clip" in n and abs(p["clip"][1] - n["clip"][0]) < 1e-6

# group contiguous runs; groups are joined by crossfades
groups = [[items[0]]]
for p, n in zip(items, items[1:]):
    if contiguous(p, n):
        groups[-1].append(n)
    else:
        groups.append([n])
inputs, f, n_in = ["-i", V, "-i", A], [], 2
glabels, gdur = [], []
for gi, g in enumerate(groups):
    ext = XF if gi < len(groups) - 1 else 0.0
    labels = []
    for ii, it in enumerate(g):
        a0, a1 = it["a"]
        dur = a1 - a0
        e = ext if ii == len(g) - 1 else 0.0
        lab = f"g{gi}_{ii}"
        if "still" in it:
            d = dur + e
            frames = round(d * FPS)
            fx, fy = it.get("focus", [0.5, 0.5])
            z = it.get("zoom", 0.07)
            inputs += ["-ss", str(it["still"]), "-i", V]
            f.append(f"[{n_in}:v]{CROP}trim=end_frame=1,loop=loop={frames}:size=1,setpts=N/{FPS}/TB,"
                     f"scale=3840:-2:flags=lanczos,zoompan=z='1+{z}*on/{frames}':x='(iw-iw/zoom)*{fx}':"
                     f"y='(ih-ih/zoom)*{fy}':d=1:s={W}x{H}:fps={FPS},unsharp=5:5:{SHARP*0.7:.2f}:5:5:0.0,"
                     f"setsar=1,format=yuv420p,trim=duration={d:.4f},settb=1/{FPS}[{lab}]")
            n_in += 1
        else:
            v0, v1 = it["clip"]
            k = dur / (v1 - v0)
            v1e = v1 + e / k
            f.append(f"[0:v]trim=start={v0}:end={v1e:.4f},setpts=(PTS-STARTPTS)*{k:.5f},{CROP}{LOOK},"
                     f"trim=duration={dur + e:.4f},settb=1/{FPS}[{lab}]")
        labels.append(f"[{lab}]")
    if len(labels) > 1:
        f.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0,settb=1/{FPS}[g{gi}]")
    else:
        f[-1] = f[-1].rsplit("[", 1)[0] + f"[g{gi}]"
    glabels.append(f"g{gi}")
    gdur.append(g[-1]["a"][1] - g[0]["a"][0])

prev, acc = glabels[0], gdur[0]
for gi in range(1, len(glabels)):
    f.append(f"[{prev}][{glabels[gi]}]xfade=transition=fade:duration={XF}:offset={acc:.4f}[x{gi}]")
    prev, acc = f"x{gi}", acc + gdur[gi]
total = items[-1]["a"][1]
burn = ""
if cfg.get("burn_captions", True) and cfg.get("srt") and os.path.exists(cfg["srt"]):
    # most desktop players (Windows Media Player, Photos) ignore soft subtitle tracks,
    # so captions are drawn into the picture as well
    srt = os.path.relpath(cfg["srt"]).replace("\\", "/").replace(":", r"\:")
    fonts = r":fontsdir='C\:/Windows/Fonts'" if os.name == "nt" else ""
    style = cfg.get("caption_style", "FontName=Segoe UI Semibold,FontSize=12,PrimaryColour=&H00FFFFFF,"
                    "BorderStyle=3,OutlineColour=&H5A000000,Outline=7,Shadow=0,MarginV=16,Alignment=2")
    burn = f",subtitles='{srt}'{fonts}:force_style='{style}'"
f.append(f"[{prev}]fade=t=in:d=0.5,fade=t=out:st={total - 0.6:.3f}:d=0.6{burn},format=yuv420p[v]")

af = f"apad=pad_dur={max(0.0, total - cfg.get('audio_len', total)):.3f}"
if cfg.get("loudnorm", True):
    # two-pass: measure first, then normalize linearly so the voice is not pumped
    ln = "loudnorm=I=-16:TP=-1.5:LRA=11"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", A, "-af", ln + ":print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    m = json.loads(r[r.rindex("{"):r.rindex("}") + 1])
    ln += (f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
           f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    af = ln + "," + af + ",aresample=48000"
f.append(f"[1:a]{af}[a]")

fscript = OUT + ".filter.txt"
open(fscript, "w").write(";\n".join(f))

meta_args = []
if cfg.get("chapters"):
    meta = OUT + ".meta.txt"
    ch = cfg["chapters"]
    with open(meta, "w", encoding="utf-8") as m:
        m.write(";FFMETADATA1\n")
        if cfg.get("title"):
            m.write(f"title={cfg['title']}\n")
        for i, c in enumerate(ch):
            end = ch[i + 1]["t"] if i + 1 < len(ch) else total
            m.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(c['t']*1000)}\nEND={int(end*1000)}\ntitle={c['title']}\n")
    inputs += ["-f", "ffmetadata", "-i", meta]
    meta_args = ["-map_metadata", str(n_in), "-map_chapters", str(n_in)]
    n_in += 1
sub_args = []
if cfg.get("srt") and os.path.exists(cfg["srt"]):
    inputs += ["-i", cfg["srt"]]
    sub_args = ["-map", f"{n_in}:s", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]
    n_in += 1

cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex_script", fscript,
       "-map", "[v]", "-map", "[a]", *sub_args, *meta_args,
       "-c:v", "libx264", "-preset", "slow", "-crf", str(cfg.get("crf", 16)),
       "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2",
       "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000",
       "-t", f"{total:.3f}", "-movflags", "+faststart", OUT]
subprocess.run(cmd, check=True)
print(f"wrote {OUT}: {len(items)} shots, {len(groups)} groups, {len(groups)-1} crossfades, {total:.2f}s")
