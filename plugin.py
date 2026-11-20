#!/usr/bin/python3
"""Shrink selected videos with ffmpeg, picking format, resolution, frame rate and quality.

Flea gives a request 30 seconds, caps the plugin at 512 MiB and kills its process group when idle,
so the pickers and the encode run as a transient systemd user unit (`plugin.py encode <paths...>`).
Choices come from Omarchy's own menu (omarchy-menu-select); results arrive through notify-send.
"""
import json
import os
import subprocess
import sys

AAC = ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
# label: (subtext, extension, video args, (high, medium, low) crf, audio args); GIF has no crf.
FORMATS = {
    "MP4 H.264": ("Plays everywhere", "mp4",
                  ["-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p"], (23, 28, 33), AAC),
    "MP4 H.265": ("Smaller file, newer devices", "mp4",
                  ["-c:v", "libx265", "-preset", "medium", "-pix_fmt", "yuv420p", "-tag:v", "hvc1",
                   "-x265-params", "log-level=error"], (26, 30, 34), AAC),
    "WebM VP9": ("For the web, slower to encode", "webm",
                 ["-c:v", "libvpx-vp9", "-b:v", "0", "-row-mt", "1", "-deadline", "good",
                  "-cpu-used", "4"], (31, 36, 42), ["-c:a", "libopus", "-b:a", "96k"]),
    "GIF": ("Silent loop", "gif", [], None, ["-an"]),
}
RESOLUTIONS = ["Original", "1080p", "720p", "480p", "360p"]
FPS = {"video": ["Original", "60", "30", "24", "15"], "gif": ["15", "10"]}
QUALITIES = ["High", "Medium", "Low"]


def pick(prompt, options):
    """One Omarchy menu; options are labels or (label, subtext). None when dismissed."""
    rows = [f"\t{o[0]}\t{o[1]}" if isinstance(o, tuple) else o for o in options]
    result = subprocess.run(["omarchy-menu-select", prompt, *rows],
                            capture_output=True, text=True, check=False)
    choice = result.stdout.strip().split("\t")[0]
    return choice if result.returncode == 0 and choice else None


def choose():
    fmt = pick("Format", [(label, spec[0]) for label, spec in FORMATS.items()])
    res = fmt and pick("Resolution", RESOLUTIONS)
    fps = res and pick("Frame rate", FPS["gif" if fmt == "GIF" else "video"])
    quality = fps and ("-" if fmt == "GIF" else pick("Quality", QUALITIES))
    return (fmt, res, fps, quality) if quality else None


def output_for(src, choice):
    fmt, res, fps, quality = choice
    parts = [res if res != "Original" else "", f"{fps}fps" if fps != "Original" else "",
             quality.lower() if quality != "-" else ""]
    stem, ext = os.path.splitext(src)[0], FORMATS[fmt][1]
    base = f"{stem}-{'-'.join(p for p in parts if p)}"
    out, n = f"{base}.{ext}", 1
    while os.path.exists(out):
        out, n = f"{base}-{n}.{ext}", n + 1
    return out


def ffmpeg_args(src, dst, choice):
    fmt, res, fps, quality = choice
    _, _, video, crfs, audio = FORMATS[fmt]
    scale = f"scale=-2:'min({res[:-1]},ih)'" if res != "Original" else ""
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n", "-i", src, "-sn"]
    if fmt == "GIF":
        chain = ",".join(f for f in (f"fps={fps}", scale and scale + ":flags=lanczos") if f)
        args += ["-vf", f"{chain},split[a][b];[a]palettegen[p];[b][p]paletteuse"]
    else:
        if scale:
            args += ["-vf", scale]
        if fps != "Original":
            args += ["-fpsmax", fps]
        args += video + ["-crf", str(crfs[QUALITIES.index(quality)])]
    return args + audio + [dst]


def notify(summary, body, urgency="normal"):
    subprocess.run(["notify-send", "-a", "Flea", "-u", urgency, summary, body], check=False)


def encode(paths):
    choice = choose()
    if not choice:
        return
    for src in paths:
        dst = output_for(src, choice)
        name = os.path.basename(src)
        notify("Shrinking video", f"{name} → {os.path.basename(dst)}")
        if subprocess.run(ffmpeg_args(src, dst, choice), check=False).returncode == 0:
            before, after = os.path.getsize(src), os.path.getsize(dst)
            notify("Video shrunk", f"{os.path.basename(dst)}\n"
                   f"{before / 2**20:.1f} MB → {after / 2**20:.1f} MB ({after / before:.0%})")
        else:
            if os.path.exists(dst):
                os.remove(dst)
            notify("Shrinking failed", name, "critical")


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
            elif op == "run" and request.get("action") == "shrink":
                paths = request.get("paths", [])
                if not paths or not all(isinstance(p, str) and os.path.isabs(p) for p in paths):
                    raise ValueError("Expected absolute selected file paths.")
                subprocess.run(["systemd-run", "--user", "--collect", "--quiet",
                                sys.executable, os.path.abspath(__file__), "encode", *paths],
                               check=True, timeout=20)
                answer({"op": "done"})
            else:
                answer({"op": "error", "message": "Unsupported action."})
        except (ValueError, OSError, TypeError, subprocess.SubprocessError) as error:
            answer({"op": "error", "message": str(error)[:4096]})


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "encode":
        encode(sys.argv[2:])
    else:
        serve()
