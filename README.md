# Stacked Metadata Simulator

**All-in-one metadata processor for images and videos — backend, hosted form, and embeddable widget in one repo.**

Built by [Stacked](https://stacked.com) · v2.4

---

## What this repo ships

This is not just a static widget. Photo/video metadata rewriting requires server-side processing: files must be uploaded, inspected, rewritten, optionally re-encoded, and returned as a ZIP. A static-only embed cannot do that safely or reliably in the browser.

This repo bundles the pieces together:

- **Processing engine** — image/video metadata injection + SynthID mitigation
- **Hosted web form** — `GET /` for customers or internal users
- **Processing API** — `POST /api/process` returns `stacked_output.zip`
- **Embed widget** — `GET /embed.js` mounts a customer-facing upload form
- **Container packaging** — Dockerfile + compose for one-command local runs and simple deploys
- **Desktop app** — original Tkinter GUI still available from source/builds

---

## Features

- **Images** — jpg, jpeg, png, tiff, webp, heic
- **Videos** — mp4, mov, avi, mkv, m4v, 3gp (`ffmpeg` required)
- **Device profiles** — iPhone 15 Pro · iPhone 14 · Samsung S24 Ultra · Pixel 8 Pro · Moto G 2024
- **GPS spoofing** — NYC, LA, Miami, London, Paris, Tokyo, Dubai, Sydney
- **Optional GPS randomization** — randomize per file, or keep the stable default location
- **Timestamp randomization** — random date within last 2 years
- **Filename randomization** — IMG_XXXXXXXX format
- **SynthID removal** — frequency-domain perturbation for images, re-encode for video
- **Website embed** — same service hosts the backend API and the JavaScript widget

---

## Quick start: one-command local service

Recommended path for local testing:

```bash
docker compose up --build
```

Open <http://127.0.0.1:8000>.

That single service includes the hosted form, `/api/process`, `/embed.js`, `/profiles`, and `/health`.

---

## Run locally without Docker

Install system dependency for videos:

```bash
# macOS
brew install ffmpeg
```

Then run the Flask service:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python web_server.py
```

Open <http://127.0.0.1:8000>.

---

## Embed on a website

Deploy this same repo as a public service, then add the widget where you want the upload form to appear:

```html
<div data-stacked-metadata-widget></div>
<script src="https://YOUR-DOMAIN.com/embed.js" data-stacked-metadata></script>
```

Because `embed.js` and `/api/process` live on the same service, the widget automatically posts uploads back to `https://YOUR-DOMAIN.com/api/process`.

If you serve the script from a CDN but keep processing on the app service, pass the API base explicitly:

```html
<div id="metadata-sim"></div>
<script
  src="https://cdn.YOUR-DOMAIN.com/embed.js"
  data-mount="#metadata-sim"
  data-api="https://app.YOUR-DOMAIN.com"
  data-stacked-metadata>
</script>
```

The widget supports multiple files, photos and videos, all device profiles, SynthID removal, and optional GPS randomization. It downloads the processed batch as `stacked_output.zip`.

---

## API

Endpoints:

- `GET /` — hosted web form
- `POST /api/process` — upload photos/videos, returns `stacked_output.zip`
- `GET /embed.js` — drop-in widget script
- `GET /profiles` — available profile keys/labels
- `GET /health` — lightweight health check

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/process \
  -F 'files=@photo.jpg' \
  -F 'files=@video.mp4' \
  -F 'profile=IPHONE_14' \
  -F 'remove_synthid=true' \
  -F 'randomize_location=true' \
  -o stacked_output.zip
```

Supported profile keys:

- `IPHONE_15`
- `IPHONE_14`
- `SAMSUNG_S24`
- `PIXEL_8`
- `MOTO_G_2024`

---

## Deploy the all-in-one service

### Generic Docker host

```bash
docker build -t stacked-metadata-sim .
docker run --rm -p 8000:8000 \
  -e STACKED_MAX_FILES=50 \
  -e STACKED_MAX_UPLOAD_MB=512 \
  stacked-metadata-sim
```

Point your domain/reverse proxy at port `8000`, then use:

```html
<div data-stacked-metadata-widget></div>
<script src="https://YOUR-DOMAIN.com/embed.js" data-stacked-metadata></script>
```

### Render / Railway / Fly.io / similar

Deploy this repository as a Docker service. The container command is already set:

```bash
gunicorn --bind ${HOST}:${PORT} --workers ${WEB_CONCURRENCY:-2} --timeout ${WEB_TIMEOUT:-300} web_server:app
```

Recommended env vars:

- `HOST=0.0.0.0`
- `PORT=8000` or the platform-provided port
- `STACKED_MAX_FILES=50`
- `STACKED_MAX_UPLOAD_MB=512`
- `WEB_TIMEOUT=300` for larger video batches

The Docker image installs `ffmpeg`, so video processing works without extra host setup.

---

## Desktop app usage

1. Click **Browse** → select your image/video folder
2. Choose a **Device Profile**
3. Toggle **Remove SynthID** if needed
4. Toggle **Randomize GPS Location** if needed
5. Hit **Start Simulation →**
6. Output lands in a `stacked_output/` subfolder — originals untouched

Run desktop app from source:

```bash
pip install -r requirements.txt
python stacked_metadata_sim.py
```

Download desktop builds from [Releases](../../releases/latest):

- `Stacked_MetadataSim_windows.exe` — Windows
- `Stacked_MetadataSim_macOS.zip` — macOS

---

## Build desktop app locally

```bash
pip install pyinstaller Pillow piexif
pyinstaller --onefile --windowed --name Stacked_MetadataSim stacked_metadata_sim.py
```

---

## License

Private — Stacked internal tool.
