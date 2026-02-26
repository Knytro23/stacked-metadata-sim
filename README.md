# Stacked Metadata Simulator

**Batch metadata injector for images and videos — with SynthID removal.**

Built by [Stacked](https://stacked.com) · v2.1

---

## Features

- **Images** — jpg, jpeg, png, tiff, webp, heic
- **Videos** — mp4, mov, avi, mkv, m4v (requires ffmpeg)
- **Device profiles** — iPhone 15 Pro · Samsung S24 Ultra · Pixel 8 Pro
- **GPS spoofing** — NYC, LA, Miami, London, Paris, Tokyo, Dubai, Sydney
- **Timestamp randomization** — random date within last 2 years
- **Filename randomization** — IMG_XXXXXXXX format
- **SynthID removal** — frequency-domain perturbation for images, re-encode for video

---

## Download

Grab the latest build from [Releases](../../releases/latest):
- `Stacked_MetadataSim_windows.exe` — Windows (double-click, no install needed)
- `Stacked_MetadataSim_macOS.zip` — macOS (.app bundle, unzip and run)

---

## Usage

1. Click **BROWSE** → select your image/video folder
2. Choose a **Device Profile**
3. Toggle **Remove SynthID** if needed
4. Hit **⚡ START SIMULATION**
5. Output lands in a `stacked_output/` subfolder — originals untouched

---

## Requirements (if running from source)

```bash
pip install Pillow piexif
python stacked_metadata_sim.py
```

**ffmpeg required for video processing:**
- macOS: `brew install ffmpeg`
- Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

---

## Build locally

```bash
pip install pyinstaller Pillow piexif
pyinstaller --onefile --windowed --name Stacked_MetadataSim stacked_metadata_sim.py
```

---

## License

Private — Stacked internal tool.
