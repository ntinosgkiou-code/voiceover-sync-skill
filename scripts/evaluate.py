"""Score a rendered sync against its config.

usage: python evaluate.py config.json [video]
Prints playback compatibility, length drift, freezes, speed extremes, loudness, and writes
<video>.cues.jpg: one frame at each cue word, to check that the click matches the words.
"""
import json, re, subprocess, sys

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2] if len(sys.argv) > 2 else cfg["out"]
run = lambda *a: subprocess.run(a, capture_output=True, text=True, encoding="utf-8", errors="replace")

probe = run("ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,profile,pix_fmt:format=duration",
            "-of", "json", out)
info = json.loads(probe.stdout)
v = next(s for s in info["streams"] if s["codec_type"] == "video")
dur = float(info["format"]["duration"])
issues = []
ok_codec = v["pix_fmt"] == "yuv420p" and v.get("profile") in ("High", "Main", "Constrained Baseline")
if not ok_codec:
    issues.append(f"codec {v.get('profile')}/{v['pix_fmt']} will not play everywhere")
print(f"codec        {v['codec_name']} {v.get('profile')} {v['pix_fmt']}  {'OK' if ok_codec else 'FAIL'}")
print(f"streams      {', '.join(s['codec_type'] for s in info['streams'])}")
target = cfg["timeline"][-1]["a"][1]
print(f"length       {dur:.2f}s (timeline {target:.2f}s, drift {dur-target:+.2f}s)")
if abs(dur - target) > 0.2:
    issues.append("length drift")

fd = run("ffmpeg", "-hide_banner", "-i", out, "-vf", "freezedetect=n=0.0005:d=1.5", "-an", "-f", "null", "-").stderr
fr = re.findall(r"freeze_start: ([\d.]+).*?freeze_duration: ([\d.]+)", fd, re.S)
print(f"freezes>1.5s {len(fr)}  " + "  ".join(f"{float(s):.1f}s({float(d):.1f})" for s, d in fr))
issues += [f"freeze at {float(s):.1f}s for {float(d):.1f}s" for s, d in fr if float(d) > 2.5]

speeds = []
for it in cfg["timeline"]:
    if "clip" in it or "parts" in it:
        src = it["clip"][1] - it["clip"][0] if "clip" in it else sum(b - a for a, b in it["parts"])
        speeds.append((src / (it["a"][1] - it["a"][0]), it["a"][0]))
lo, hi = min(speeds), max(speeds)
print(f"speed range  {lo[0]:.2f}x (at {lo[1]:.1f}s) .. {hi[0]:.2f}x (at {hi[1]:.1f}s)")
issues += [f"fast-forward {s:.1f}x at {t:.1f}s" for s, t in speeds if s > 2.2]
issues += [f"slow motion {s:.2f}x at {t:.1f}s" for s, t in speeds if s < 0.4]

lu = run("ffmpeg", "-hide_banner", "-i", out, "-af", "ebur128", "-vn", "-f", "null", "-").stderr
m = re.findall(r"I:\s+(-?[\d.]+) LUFS", lu)
if m:
    print(f"loudness     {m[-1]} LUFS (target -16)")
    if abs(float(m[-1]) + 16) > 2:
        issues.append(f"loudness {m[-1]} LUFS")

if cfg.get("cues"):
    sheet = out + ".cues.jpg"
    args, fl = [], []
    for i, c in enumerate(cfg["cues"]):
        args += ["-ss", str(c["a"]), "-i", out]
        fl.append(f"[{i}:v]trim=end_frame=1,scale=480:-2,drawbox=y=ih-28:h=28:w=iw:color=black@0.7:t=fill[c{i}]")
    n = len(cfg["cues"]); cols = 4; rows = -(-n // cols)
    fl.append("".join(f"[c{i}]" for i in range(n)) +
              f"xstack=inputs={n}:layout=" + "|".join(f"{(i%cols)*480}_{(i//cols)*264}" for i in range(n)) +
              f":fill=black[o]")
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args, "-filter_complex", ";".join(fl),
        "-map", "[o]", "-frames:v", "1", sheet)
    print(f"cue sheet    {sheet}  (order: " + " | ".join(c["label"] for c in cfg["cues"]) + ")")

print("\nISSUES: " + ("none" if not issues else "\n - " + "\n - ".join(issues)))
