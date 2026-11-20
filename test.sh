#!/usr/bin/env bash
# Encodes a generated clip with every format, answering Omarchy's menu with a stub, and checks the outputs.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

mkdir "$work/bin"
cat >"$work/bin/omarchy-menu-select" <<'EOF'
#!/usr/bin/env bash
case $1 in Format) echo "$FMT" ;; Resolution) echo "$RES" ;; "Frame rate") echo "$FPS" ;; Quality) echo Medium ;; esac
EOF
printf '#!/bin/sh\n' >"$work/bin/notify-send"
chmod +x "$work/bin/"*
export PATH="$work/bin:$PATH"

ffmpeg -loglevel error -f lavfi -i testsrc2=size=1920x1080:rate=60:duration=3 -f lavfi -i sine=duration=3 \
  -c:v libx264 -crf 12 -c:a aac "$work/clip one.mp4"

check() { # format resolution fps expected-file expected-WxH,fps
  FMT=$1 RES=$2 FPS=$3 python3 "$here/plugin.py" encode "$work/clip one.mp4"
  got=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,avg_frame_rate -of csv=p=0 "$work/$4")
  [[ $got == "$5" ]] || { echo "FAIL $1 $2 $3: $got != $5"; exit 1; }
  echo "ok  $4  $got  $(du -h "$work/$4" | cut -f1)"
}
check "MP4 H.264" Original Original "clip one-medium.mp4" "1920,1080,60/1"
check "MP4 H.264" 720p 30 "clip one-720p-30fps-medium.mp4" "1280,720,30/1"
check "MP4 H.264" 720p 30 "clip one-720p-30fps-medium-1.mp4" "1280,720,30/1"
check "MP4 H.265" 480p 24 "clip one-480p-24fps-medium.mp4" "854,480,24/1"
check "WebM VP9" 360p 15 "clip one-360p-15fps-medium.webm" "640,360,15/1"
check "GIF" 360p 10 "clip one-360p-10fps.gif" "640,360,10/1"
FMT= python3 "$here/plugin.py" encode "$work/clip one.mp4"  # dismissed menu writes nothing
[[ $(ls "$work" | wc -l) == 8 ]] || { echo "FAIL dismissed menu wrote a file"; exit 1; }
echo "all ok"
