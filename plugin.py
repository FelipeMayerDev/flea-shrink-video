#!/usr/bin/env python3
"""Compress selected videos with ffmpeg presets.

Flea gives a request 30 seconds, caps the plugin at 512 MiB and kills its process group when idle,
so the encode runs as a transient systemd user unit (`plugin.py encode <preset> <paths...>`)
and reports through notify-send.
"""
import json
import os
import subprocess
import sys

# preset: (crf, extra video filters, max fps or None)
PRESETS = {
    "balanced": (28, [], None),
    "small": (33, [], None),
    "fps30": (28, [], 30),
    "hd720": (28, ["scale=-2:'min(720,ih)'"], 30),
    "tiny": (32, ["scale=-2:'min(480,ih)'"], 24),
}


def output_for(path, preset):
    stem = os.path.splitext(path)[0]
    out, n = f"{stem}-{preset}.mp4", 1
    while os.path.exists(out):
        out, n = f"{stem}-{preset}-{n}.mp4", n + 1
    return out


def ffmpeg_args(src, dst, preset):
    crf, filters, fps = PRESETS[preset]
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n", "-i", src]
    if filters:
        args += ["-vf", ",".join(filters)]
    if fps:
        args += ["-fpsmax", str(fps)]
    return args + ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-b:a", "128k", "-sn", "-movflags", "+faststart", dst]


def notify(summary, body, urgency="normal"):
    subprocess.run(["notify-send", "-a", "Flea", "-u", urgency, summary, body], check=False)


def encode(preset, paths):
    for src in paths:
        dst = output_for(src, preset)
        name = os.path.basename(src)
        if subprocess.run(ffmpeg_args(src, dst, preset), check=False).returncode == 0:
            before, after = os.path.getsize(src), os.path.getsize(dst)
            notify("Video compressed", f"{os.path.basename(dst)}\n"
                   f"{before / 2**20:.1f} MB → {after / 2**20:.1f} MB ({after / before:.0%})")
        else:
            if os.path.exists(dst):
                os.remove(dst)
            notify("Compression failed", name, "critical")


def answer(value):
    print(json.dumps(value), flush=True)


def serve():
    for line in iter(lambda: sys.stdin.buffer.readline(65538), b""):
        try:
            request = json.loads(line)
            op = request.get("op")
            if op == "hello":
                answer({"op": "ready", "protocolVersion": 1})
            elif op == "settings":
                answer({"op": "done"})
            elif op == "cancel":
                break
            elif op == "run" and request.get("action") in PRESETS:
                paths = request.get("paths", [])
                if not paths or not all(isinstance(p, str) and os.path.isabs(p) for p in paths):
                    raise ValueError("Expected absolute selected file paths.")
                subprocess.run(["systemd-run", "--user", "--collect", "--quiet",
                                sys.executable, os.path.abspath(__file__), "encode",
                                request["action"], *paths], check=True, timeout=20)
                answer({"op": "done", "message": f"Compressing {len(paths)} video(s) in the "
                        "background. A notification will appear when done."})
            else:
                answer({"op": "error", "message": "Unsupported action."})
        except (ValueError, OSError, TypeError, subprocess.SubprocessError) as error:
            answer({"op": "error", "message": str(error)[:4096]})


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "encode" and sys.argv[2] in PRESETS:
        encode(sys.argv[2], sys.argv[3:])
    else:
        serve()
