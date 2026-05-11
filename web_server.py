"""
Website-embeddable server for Meta Data Simulator.

Run:
    python web_server.py

Embed on another site:
    <script src="https://your-domain.com/embed.js" data-metadata-simulator></script>
"""
from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from flask import Flask, Response, jsonify, render_template_string, request, send_file
from werkzeug.utils import secure_filename

from metadata_simulator import (
    IMAGE_EXTS,
    PIL_AVAILABLE,
    PROFILES,
    VIDEO_EXTS,
    process_image,
    process_video,
)

ALLOWED_EXTS = IMAGE_EXTS | VIDEO_EXTS
MAX_FILES = int(os.environ.get("METADATA_SIM_MAX_FILES", "50"))
MAX_UPLOAD_MB = int(os.environ.get("METADATA_SIM_MAX_UPLOAD_MB", "512"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


@app.after_request
def add_embed_headers(response):
    # Allows the widget to be hosted on one domain and embedded elsewhere.
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
    return response


@app.get("/health")
def health():
    return jsonify({"ok": True, "profiles": list(PROFILES.keys())})


@app.get("/profiles")
def profiles():
    return jsonify({key: value["label"] for key, value in PROFILES.items()})


@app.route("/api/process", methods=["POST", "OPTIONS"])
def api_process():
    if request.method == "OPTIONS":
        return Response(status=204)
    if not PIL_AVAILABLE:
        return jsonify({"error": "Missing dependencies. Install Pillow and piexif."}), 500

    uploads = request.files.getlist("files")
    if not uploads:
        upload = request.files.get("file")
        uploads = [upload] if upload else []
    uploads = [f for f in uploads if f and f.filename]

    if not uploads:
        return jsonify({"error": "Upload at least one photo or video."}), 400
    if len(uploads) > MAX_FILES:
        return jsonify({"error": f"Too many files. Max is {MAX_FILES}."}), 400

    profile = request.form.get("profile", "IPHONE_15")
    if profile not in PROFILES:
        return jsonify({"error": f"Unknown profile: {profile}"}), 400

    remove_synthid = _truthy(request.form.get("remove_synthid", "true"))
    randomize_location = _truthy(request.form.get("randomize_location", "true"))

    tmp_root = Path(tempfile.mkdtemp(prefix="metadata_simulator_"))
    in_dir = tmp_root / "input"
    out_dir = tmp_root / "output"
    in_dir.mkdir()
    out_dir.mkdir()
    logs: list[str] = []

    try:
        saved: list[Path] = []
        for upload in uploads:
            filename = secure_filename(upload.filename)
            ext = Path(filename).suffix.lower()
            if ext not in ALLOWED_EXTS:
                logs.append(f"skip {filename}: unsupported extension")
                continue
            target = in_dir / filename
            upload.save(target)
            saved.append(target)

        if not saved:
            return jsonify({"error": "No supported media files uploaded."}), 400

        ok = fail = 0
        for src in saved:
            try:
                ext = src.suffix.lower()
                if ext in IMAGE_EXTS:
                    process_image(str(src), str(out_dir), profile, remove_synthid, logs.append, randomize_location)
                else:
                    process_video(str(src), str(out_dir), profile, remove_synthid, logs.append, randomize_location)
                ok += 1
            except Exception as exc:  # return the rest instead of failing the full batch
                logs.append(f"✗ {src.name} → {exc}")
                fail += 1

        if ok == 0:
            return jsonify({"error": "Processing failed for every file.", "logs": logs}), 422

        zip_path = tmp_root / "metadata_output.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in out_dir.iterdir():
                if file.is_file():
                    zf.write(file, arcname=file.name)
            zf.writestr("processing-log.txt", "\n".join(logs) + "\n")

        response = send_file(
            zip_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name="metadata_output.zip",
        )
        response.call_on_close(lambda: shutil.rmtree(tmp_root, ignore_errors=True))
        response.headers["X-MetadataSim-Processed"] = str(ok)
        response.headers["X-MetadataSim-Failed"] = str(fail)
        return response
    except Exception:
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise


@app.get("/")
def index():
    return render_template_string(PAGE_HTML, profiles=PROFILES)


@app.get("/embed.js")
def embed_js():
    return Response(EMBED_JS, mimetype="application/javascript; charset=utf-8")


def _truthy(value: str | None) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}


PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meta Data Simulator</title>
  <style>
    body{margin:0;background:#111;color:#fff;font:16px/1.4 Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:40px}
    main{max-width:720px;margin:0 auto;background:#1a1a1a;border:1px solid #2a2a2a;border-radius:20px;padding:28px}
    h1{margin:0 0 8px;font-size:34px;letter-spacing:-.03em}.sub{color:#999;margin-bottom:24px}
    label{display:block;color:#aaa;font-size:12px;font-weight:700;text-transform:uppercase;margin:18px 0 8px}
    input,select,button{font:inherit} input[type=file],select{box-sizing:border-box;width:100%;background:#111;color:#fff;border:1px solid #333;border-radius:12px;padding:14px}
    .check{display:flex;gap:10px;align-items:center;color:#ddd;margin:12px 0}.check input{width:auto}
    button{background:#fff;color:#000;border:0;border-radius:999px;padding:14px 20px;font-weight:800;cursor:pointer;margin-top:18px}
    #status{color:#aaa;margin-top:16px;white-space:pre-wrap}
  </style>
</head>
<body><main>
  <h1>Inject. Spoof. Ship.</h1>
  <div class="sub">Batch metadata simulation for photos and videos.</div>
  <div data-metadata-simulator-widget></div>
</main><script src="/embed.js"></script></body></html>
"""

EMBED_JS = r"""
(() => {
  const script = document.currentScript;
  const base = (script?.dataset.api || script?.src?.replace(/\/embed\.js(?:\?.*)?$/, '') || '').replace(/\/$/, '');
  const mount = document.querySelector(script?.dataset.mount || '[data-metadata-simulator-widget]') || script?.parentElement || document.body;
  const css = `
    .metadata-simulator-widget{box-sizing:border-box;max-width:560px;background:#111;color:#fff;border:1px solid #2a2a2a;border-radius:18px;padding:22px;font:15px/1.35 Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .metadata-simulator-widget *{box-sizing:border-box}.metadata-simulator-widget h3{margin:0 0 6px;font-size:24px;letter-spacing:-.03em}.metadata-simulator-widget p{margin:0 0 18px;color:#999}
    .metadata-simulator-widget label{display:block;color:#aaa;font-size:11px;font-weight:800;text-transform:uppercase;margin:14px 0 7px}.metadata-simulator-widget input[type=file],.metadata-simulator-widget select{width:100%;background:#1a1a1a;color:#fff;border:1px solid #333;border-radius:12px;padding:12px}
    .metadata-simulator-widget .row{display:flex;gap:10px;align-items:center;color:#ddd;margin:10px 0}.metadata-simulator-widget button{background:#fff;color:#000;border:0;border-radius:999px;padding:12px 16px;font-weight:800;cursor:pointer;margin-top:14px}.metadata-simulator-widget .status{color:#aaa;margin-top:12px;white-space:pre-wrap}
  `;
  const style = document.createElement('style'); style.textContent = css; document.head.appendChild(style);
  const wrap = document.createElement('div'); wrap.className = 'metadata-simulator-widget';
  wrap.innerHTML = `
    <h3>Meta Data Simulator</h3><p>Process photos and videos, then download a clean ZIP.</p>
    <form><label>Photos / Videos</label><input name="files" type="file" multiple accept="image/*,video/*" required>
    <label>Device Profile</label><select name="profile">
      <option value="IPHONE_15">iPhone 15 Pro</option><option value="IPHONE_14">iPhone 14</option><option value="SAMSUNG_S24">Samsung S24 Ultra</option><option value="PIXEL_8">Pixel 8 Pro</option><option value="MOTO_G_2024">Moto G 2024</option>
    </select>
    <label class="row"><input name="remove_synthid" type="checkbox" checked> Remove SynthID watermark</label>
    <label class="row"><input name="randomize_location" type="checkbox" checked> Randomize GPS location</label>
    <button>Start Simulation →</button><div class="status"></div></form>`;
  mount.appendChild(wrap);
  const form = wrap.querySelector('form'); const status = wrap.querySelector('.status'); const button = wrap.querySelector('button');
  form.addEventListener('submit', async (event) => {
    event.preventDefault(); button.disabled = true; status.textContent = 'Processing…';
    const data = new FormData(form);
    if (!form.elements.remove_synthid.checked) data.set('remove_synthid', 'false');
    if (!form.elements.randomize_location.checked) data.set('randomize_location', 'false');
    try {
      const res = await fetch(`${base}/api/process`, { method: 'POST', body: data });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `Request failed (${res.status})`);
      const blob = await res.blob(); const url = URL.createObjectURL(blob); const a = document.createElement('a');
      a.href = url; a.download = 'metadata_output.zip'; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
      status.textContent = `Done. Processed ${res.headers.get('X-MetadataSim-Processed') || '?'} file(s).`;
    } catch (err) { status.textContent = err.message || String(err); }
    finally { button.disabled = false; }
  });
})();
"""


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))
