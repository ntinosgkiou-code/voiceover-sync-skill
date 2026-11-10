"""Map a screen recording so its actions can be matched to a voiceover.

usage: python scan.py video.mp4 outdir [--crop W:H:X:Y] [--fine START END]
Writes to outdir:
  scenes.txt      timestamps of visual changes (clicks, dialogs, page loads)
  sheet_N.jpg     1 frame per second, 6x6 per sheet, row-major from 0 s (index = second)
  fine.jpg        with --fine: 5 frames per second between START and END (find the exact click)
  frame_T.png     full-resolution frame at 20% of the duration (pick the crop box from it)
"""
import json, os, re, subprocess, sys

args = sys.argv[1:]
video, out = args[0], args[1]
crop = args[args.index("--crop") + 1] if "--crop" in args else None
os.makedirs(out, exist_ok=True)
c = f"crop={crop}," if crop else ""
q = lambda *a: subprocess.run(a, capture_output=True, text=True, encoding="utf-8", errors="replace")

if "--fine" in args:
    i = args.index("--fine")
    s, e = float(args[i + 1]), float(args[i + 2])
    n = int((e - s) * 5)
    cols = 5
    q("ffmpeg", "-y", "-loglevel", "error", "-ss", str(s), "-t", str(e - s), "-i", video, "-vf",
      f"fps=5,{c}scale=320:-2,tile={cols}x{-(-n // cols)}", "-frames:v", "1", os.path.join(out, "fine.jpg"))
    print(f"fine.jpg: frame k is at {s} + 0.2*k s")
    sys.exit()

info = json.loads(q("ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,r_frame_rate",
                    "-of", "json", video).stdout)
dur = float(info["format"]["duration"])
print(f"duration {dur:.2f}s, streams {info['streams']}")

sc = q("ffmpeg", "-hide_banner", "-i", video, "-vf", f"{c}select='gt(scene,0.08)',showinfo", "-an", "-f", "null", "-").stderr
times = [float(t) for t in re.findall(r"pts_time:([\d.]+)", sc)]
open(os.path.join(out, "scenes.txt"), "w").write("\n".join(f"{t:.2f}" for t in times))
print(f"{len(times)} scene changes -> scenes.txt")

sheets = -(-int(dur) // 36)
q("ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vf", f"fps=1,{c}scale=300:-2,tile=6x6",
  "-frames:v", str(sheets), os.path.join(out, "sheet_%d.jpg"))
t = round(dur * 0.2, 1)
q("ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", video, "-frames:v", "1", os.path.join(out, f"frame_{t}.png"))
print(f"{sheets} contact sheets (sheet N, index i => second 36*(N-1)+i); full frame at {t}s")
