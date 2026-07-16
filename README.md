# Meta Data Simulator

**All-in-one metadata processor for images and videos — backend, hosted form, and embeddable widget in one repo.**

## What this repo ships

This is not just a static widget. Photo/video metadata rewriting requires server-side processing: files must be uploaded, inspected, rewritten, optionally re-encoded, and returned as a ZIP. A static-only embed cannot do that safely or reliably in the browser.

This repo bundles the pieces together:

- **Processing engine** — image/video metadata injection + SynthID mitigation
- **Hosted web form** — `GET /` for customers or internal users
- **Processing API** — `POST /api/process` returns `metadata_output.zip`
- **Embed widget** — `GET /embed.js` mounts a customer-facing upload form
- **Container packaging** — Dockerfile + compose for one-command local runs and simple deploys
- **Desktop app** — original Tkinter GUI still available from source/builds

---

## Features

- **Images** — jpg, jpeg, png, tiff, webp, heic (HEIC decoded via `pillow-heif`; output is re-encoded JPEG)
- **Videos** — mp4, mov, avi, mkv, m4v, 3gp (`ffmpeg` required)
- **Device-matched profiles** — iPhone 15 · iPhone 15 Pro · iPhone 14 · Pixel 8. A swarm device's model string (`iphone15,4`, `iPhone 15 Pro`, …) resolves to the right profile automatically via `resolve_profile()`, so each post is spoofed to match the device it's dispatched to.
- **US-only GPS** — Los Angeles · Birmingham AL · New York City · Miami, each jittered ~5 km per file so no two posts of the same source image share a GPS point.
- **Fresh-per-post metadata** — filename (`IMG_####XXXX`), capture timestamp, and GPS are re-randomized on every call; the same source image never yields identical metadata twice.
- **Coherent capture data** — DateTimeOriginal, GPS date/time, altitude, and video `creation_time` are all derived from one timestamp per file.
- **AI / SynthID mitigation** — all source EXIF/XMP/C2PA provenance is dropped (image EXIF rebuilt from scratch; video `-map_metadata -1`), plus a pixel-domain perturbation + re-encode to degrade invisible watermarks.
- **Server-to-server API** — `POST /api/process-one` returns one processed file with a `X-MetadataSim-Verified` header; token-authenticated for internal callers.

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
<div data-metadata-simulator-widget></div>
<script src="https://YOUR-DOMAIN.com/embed.js" data-metadata-simulator></script>
```

Because `embed.js` and `/api/process` live on the same service, the widget automatically posts uploads back to `https://YOUR-DOMAIN.com/api/process`.

If you serve the script from a CDN but keep processing on the app service, pass the API base explicitly:

```html
<div id="metadata-sim"></div>
<script
  src="https://cdn.YOUR-DOMAIN.com/embed.js"
  data-mount="#metadata-sim"
  data-api="https://app.YOUR-DOMAIN.com"
  data-metadata-simulator>
</script>
```

The widget supports multiple files, photos and videos, all device profiles, SynthID removal, and optional GPS randomization. It downloads the processed batch as `metadata_output.zip`.

---

## API

Endpoints:

- `POST /api/process-one` — **server-to-server**: one file in (`file`), one processed file out, with `X-MetadataSim-*` headers. This is what swarm-service calls per post.
- `POST /api/process` — batch: upload photos/videos, returns `metadata_output.zip`
- `GET /verify` — self-check: processes a synthetic image and returns `{ok:true}` only if the spoof took effect (metadata matches profile + US GPS). Use as a health probe.
- `GET /profiles` — available profile keys/labels
- `GET /health` — lightweight health check
- `GET /` and `GET /embed.js` — public web form + widget, **disabled unless `METADATA_SIM_ENABLE_EMBED=1`**

Auth: when `METADATA_SIM_TOKEN` is set, the processing endpoints require header `X-MetadataSim-Token: <token>`. Leave unset only for local dev.

`process-one` accepts either `profile` (explicit key) or `device_model` (the swarm device's model string, resolved automatically):

```bash
curl -X POST http://127.0.0.1:8000/api/process-one \
  -H 'X-MetadataSim-Token: <token>' \
  -F 'file=@photo.jpg' \
  -F 'device_model=iphone15,4' \
  -F 'remove_synthid=true' \
  -F 'randomize_location=true' \
  -D - -o processed.jpg
# → X-MetadataSim-Profile: IPHONE_15
#   X-MetadataSim-Verified: true
```

Supported profile keys: `IPHONE_15`, `IPHONE_15_PRO`, `IPHONE_14`, `PIXEL_8`.
Model-string resolution lives in `DEVICE_MODEL_MAP` (unknown iPhones → `IPHONE_15`, unknown Androids → `PIXEL_8`).

---

## Deploy the all-in-one service

### Generic Docker host

```bash
docker build -t metadata-simulator .
docker run --rm -p 8000:8000 \
  -e METADATA_SIM_MAX_FILES=50 \
  -e METADATA_SIM_MAX_UPLOAD_MB=512 \
  metadata-simulator
```

Point your domain/reverse proxy at port `8000`, then use:

```html
<div data-metadata-simulator-widget></div>
<script src="https://YOUR-DOMAIN.com/embed.js" data-metadata-simulator></script>
```

### Render / Railway / Fly.io / similar

Deploy this repository as a Docker service. The container command is already set:

```bash
gunicorn --bind ${HOST}:${PORT} --workers ${WEB_CONCURRENCY:-2} --timeout ${WEB_TIMEOUT:-300} web_server:app
```

Recommended env vars:

- `HOST=0.0.0.0`
- `PORT=8000` or the platform-provided port
- `METADATA_SIM_TOKEN=<shared-secret>` — **required in prod**; callers send it as `X-MetadataSim-Token`
- `METADATA_SIM_ENABLE_EMBED=0` — keep the public form/widget off for an internal service
- `METADATA_SIM_MAX_FILES=50`
- `METADATA_SIM_MAX_UPLOAD_MB=512`
- `WEB_TIMEOUT=300` for larger video batches

The Docker image installs `ffmpeg`, so video processing works without extra host setup.

---

## Desktop app usage

1. Click **Browse** → select your image/video folder
2. Choose a **Device Profile**
3. Toggle **Remove SynthID** if needed
4. Toggle **Randomize GPS Location** if needed
5. Hit **Start Simulation →**
6. Output lands in a `metadata_output/` subfolder — originals untouched

Run desktop app from source:

```bash
pip install -r requirements.txt
python metadata_simulator.py
```

Download desktop builds from [Releases](../../releases/latest):

- `MetaDataSimulator_Windows.exe` — Windows
- `MetaDataSimulator_macOS.zip` — macOS

---

## Build desktop app locally

```bash
pip install pyinstaller Pillow piexif
pyinstaller --onefile --windowed --name MetaDataSimulator metadata_simulator.py
```

---

## License

Private internal tool.
