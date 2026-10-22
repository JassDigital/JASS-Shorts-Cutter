# JASS Creator Studio v0.1.0

A free Windows desktop video cutter foundation for YouTube Shorts, Facebook Stories, and Instagram Stories.

## Features in v0.1.0
- Dark desktop UI
- Import and preview video files
- Clip list
- Platform export presets
- Trim the selected clip using start and end times
- Export H.264/AAC MP4 using FFmpeg
- Portrait 1080x1920 crop or fit-with-blurred-background mode

## Requirements
- Python 3.10+
- PySide6
- FFmpeg and FFprobe available on PATH

## Install
```powershell
py -m pip install -r requirements.txt
```

Install FFmpeg from https://ffmpeg.org/download.html and ensure `ffmpeg -version` works in PowerShell.

## Run
```powershell
py run.py
```

## Notes
This is the first foundation version. In this version, export processes the selected clip. Multi-clip concatenation, accurate preview crop, export cancellation, and richer progress reporting are planned for subsequent versions.
