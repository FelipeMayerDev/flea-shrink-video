# Flea Video Compressor

A [Flea](https://github.com/thisisgm/flea) plugin that adds ffmpeg compression presets to the
right-click menu of video files.

| Menu row | What it does |
| --- | --- |
| Compress: Keep FPS | Same resolution and frame rate, H.264 CRF 28 |
| Compress: Lower Quality | Same resolution and frame rate, H.264 CRF 33 |
| Compress: 30 FPS | Caps the frame rate at 30, CRF 28 |
| Compress: 720p, 30 FPS | Scales down to 720p (never up), caps at 30 FPS, CRF 28 |
| Compress: 480p, 24 FPS | Scales down to 480p, caps at 24 FPS, CRF 32 |

The output is an MP4 (H.264 + AAC 128k) written next to the original as `<name>-<preset>.mp4`.
The original is never touched, and an existing output is never overwritten.

Encoding runs in the background as a transient systemd user unit, so a long video is not cut by
Flea's 30-second plugin request limit. A notification shows the size before and after when it
finishes. Several selected videos are encoded one after another.

## Requirements

- Flea 0.4.0 or newer
- `ffmpeg` with `libx264`, `systemd-run`, `notify-send`
- Python 3

## Install

```sh
flea plugin add https://github.com/FelipeMayerDev/flea-video-compressor.git
flea plugin enable felipemayerdev.video-compressor
```

Restart Flea if an already open window does not show the new rows.

Update with `flea plugin update felipemayerdev.video-compressor`.

## Uninstall

```sh
flea plugin remove felipemayerdev.video-compressor
```

## Tweaking presets

The presets live in the `PRESETS` table at the top of `plugin.py`: CRF, extra ffmpeg video
filters and maximum frame rate. Lower CRF means better quality and a bigger file.

## License

MIT
