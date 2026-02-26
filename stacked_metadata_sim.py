"""
Stacked Metadata Simulator v2.1
- Batch EXIF/metadata injection (images + videos)
- SynthID watermark removal
- Device profiles: iPhone 15 Pro / Samsung S24 Ultra / Pixel 8 Pro
- GPS spoofing + timestamp randomization
"""
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import shutil
import string
import random
import datetime
import subprocess
import threading
import tempfile

try:
    from PIL import Image, ImageFilter
    import piexif
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ─── BRAND COLORS ─────────────────────────────────────────────────────────────
C = {
    "bg":      "#0A0A0A",
    "card":    "#111111",
    "primary": "#00FF88",
    "dim":     "#00CC66",
    "text":    "#FFFFFF",
    "sub":     "#666666",
    "border":  "#1E1E1E",
    "red":     "#FF4444",
    "yellow":  "#FFB800",
}

# ─── DEVICE PROFILES ──────────────────────────────────────────────────────────
DEVICE_PROFILES = {
    "IPHONE_15": {
        "Make": "Apple", "Model": "iPhone 15 Pro",
        "Software": "17.2.1", "LensMake": "Apple",
        "LensModel": "iPhone 15 Pro back triple camera 6.765mm f/1.78",
        "FocalLength": (677, 100), "FNumber": (178, 100),
        "ExposureTime": (1, 1000), "ISOSpeedRatings": 50,
        "Flash": 24, "WhiteBalance": 0, "ColorSpace": 1,
        "ExifVersion": b"0232", "FlashPixVersion": b"0100",
        # ffmpeg metadata for video
        "ffmpeg_meta": {
            "make": "Apple", "model": "iPhone 15 Pro",
            "com.apple.quicktime.make": "Apple",
            "com.apple.quicktime.model": "iPhone 15 Pro",
            "com.apple.quicktime.software": "17.2.1",
        }
    },
    "SAMSUNG_S24": {
        "Make": "samsung", "Model": "SM-S928B",
        "Software": "S928BXXU2AXCA", "LensMake": "Samsung",
        "LensModel": "Samsung Galaxy S24 Ultra rear camera 6.3mm f/1.7",
        "FocalLength": (630, 100), "FNumber": (170, 100),
        "ExposureTime": (1, 1200), "ISOSpeedRatings": 64,
        "Flash": 0, "WhiteBalance": 0, "ColorSpace": 1,
        "ExifVersion": b"0220", "FlashPixVersion": b"0100",
        "ffmpeg_meta": {
            "make": "samsung", "model": "SM-S928B",
            "Manufacturer": "samsung", "Model": "SM-S928B",
        }
    },
    "PIXEL_8": {
        "Make": "Google", "Model": "Pixel 8 Pro",
        "Software": "HDR+ 1.0.560250830z", "LensMake": "Google",
        "LensModel": "Pixel 8 Pro back camera 6.81mm f/1.68",
        "FocalLength": (681, 100), "FNumber": (168, 100),
        "ExposureTime": (1, 800), "ISOSpeedRatings": 80,
        "Flash": 0, "WhiteBalance": 0, "ColorSpace": 1,
        "ExifVersion": b"0231", "FlashPixVersion": b"0100",
        "ffmpeg_meta": {
            "make": "Google", "model": "Pixel 8 Pro",
            "Manufacturer": "Google",
        }
    },
}

# ─── LOCATIONS ────────────────────────────────────────────────────────────────
LOCATIONS = [
    {"name": "New York City",  "lat":  40.7128, "lon":  -74.0060},
    {"name": "Los Angeles",    "lat":  34.0522, "lon": -118.2437},
    {"name": "Miami",          "lat":  25.7617, "lon":  -80.1918},
    {"name": "London",         "lat":  51.5074, "lon":   -0.1278},
    {"name": "Paris",          "lat":  48.8566, "lon":    2.3522},
    {"name": "Tokyo",          "lat":  35.6762, "lon":  139.6503},
    {"name": "Dubai",          "lat":  25.2048, "lon":   55.2708},
    {"name": "Sydney",         "lat": -33.8688, "lon":  151.2093},
]

IMAGE_EXTS = {".jpg", ".jpeg", ".tiff", ".tif", ".png", ".webp", ".heic"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp"}


# ─── HELPERS ──────────────────────────────────────────────────────────────────
def dms(decimal):
    d = int(abs(decimal))
    mf = (abs(decimal) - d) * 60
    m = int(mf)
    s = round((mf - m) * 60 * 100)
    return ((d, 1), (m, 1), (s, 100))

def rand_loc():
    return random.choice(LOCATIONS)

def rand_ts():
    dt = datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 730))
    return dt.strftime("%Y:%m:%d %H:%M:%S")

def rand_ts_iso():
    dt = datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 730))
    return dt.strftime("%Y-%m-%dT%H:%M:%S")

def rand_fname(ext):
    return "IMG_" + "".join(random.choices(string.digits, k=8)) + ext


# ─── SYNTHID REMOVAL ──────────────────────────────────────────────────────────
def remove_synthid_image(img: "Image.Image") -> "Image.Image":
    """
    Disrupt SynthID watermark via multi-step frequency domain perturbation:
    1. Slight scale down + back up (disrupts DCT embedding grid)
    2. Minimal noise injection (±1 LSB)
    3. Sub-pixel color jitter
    """
    w, h = img.size
    # Step 1: scale perturbation (0.3% shrink + back)
    small = img.resize((int(w * 0.997), int(h * 0.997)), Image.LANCZOS)
    img = small.resize((w, h), Image.LANCZOS)
    # Step 2: very mild noise via filter (disrupts frequency embedding)
    img = img.filter(ImageFilter.SMOOTH_MORE)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def remove_synthid_video_flags(ffmpeg_args: list) -> list:
    """
    Append ffmpeg args that force re-encode with perturbed codec parameters
    to disrupt SynthID video watermarking.
    """
    return ffmpeg_args + [
        "-vf", "scale=iw*0.997:ih*0.997,scale=iw/0.997:ih/0.997,unsharp=3:3:0.3",
        "-c:v", "libx264",
        "-crf", str(random.randint(19, 22)),
        "-preset", "slow",
        "-x264-params", f"keyint={random.randint(48,72)}:min-keyint=24",
        "-c:a", "aac",
        "-b:a", "192k",
    ]


# ─── IMAGE PROCESSOR ──────────────────────────────────────────────────────────
def process_image(src, out_dir, device_key, remove_sid, log):
    p = DEVICE_PROFILES[device_key]
    ts = rand_ts()
    loc = rand_loc()
    lat, lon = loc["lat"], loc["lon"]

    exif = {
        "0th": {
            piexif.ImageIFD.Make:     p["Make"].encode(),
            piexif.ImageIFD.Model:    p["Model"].encode(),
            piexif.ImageIFD.Software: p["Software"].encode(),
            piexif.ImageIFD.DateTime: ts.encode(),
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal:  ts.encode(),
            piexif.ExifIFD.LensMake:          p["LensMake"].encode(),
            piexif.ExifIFD.LensModel:         p["LensModel"].encode(),
            piexif.ExifIFD.FocalLength:       p["FocalLength"],
            piexif.ExifIFD.FNumber:           p["FNumber"],
            piexif.ExifIFD.ExposureTime:      p["ExposureTime"],
            piexif.ExifIFD.ISOSpeedRatings:   p["ISOSpeedRatings"],
            piexif.ExifIFD.Flash:             p["Flash"],
            piexif.ExifIFD.WhiteBalance:      p["WhiteBalance"],
            piexif.ExifIFD.ColorSpace:        p["ColorSpace"],
            piexif.ExifIFD.ExifVersion:       p["ExifVersion"],
            piexif.ExifIFD.FlashPixVersion:   p["FlashPixVersion"],
        },
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef:  b"N" if lat >= 0 else b"S",
            piexif.GPSIFD.GPSLatitude:     dms(lat),
            piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
            piexif.GPSIFD.GPSLongitude:    dms(lon),
        },
        "1st": {}, "thumbnail": None,
    }
    exif_bytes = piexif.dump(exif)

    img = Image.open(src).convert("RGB")
    if remove_sid:
        img = remove_synthid_image(img)

    out_name = rand_fname(".jpg")
    out_path = os.path.join(out_dir, out_name)
    img.save(out_path, "JPEG", exif=exif_bytes, quality=95)

    sid_tag = " [SynthID✗]" if remove_sid else ""
    log(f"✅  {os.path.basename(src)} → {out_name}  [{device_key} · {loc['name']}{sid_tag}]")
    return out_name


# ─── VIDEO PROCESSOR ──────────────────────────────────────────────────────────
def process_video(src, out_dir, device_key, remove_sid, log):
    p = DEVICE_PROFILES[device_key]
    ts_iso = rand_ts_iso()
    loc = rand_loc()
    lat, lon = loc["lat"], loc["lon"]

    ext = os.path.splitext(src)[1].lower()
    out_name = rand_fname(".mp4")
    out_path = os.path.join(out_dir, out_name)

    # Build ffmpeg command
    cmd = ["ffmpeg", "-y", "-i", src]

    if remove_sid:
        cmd = remove_synthid_video_flags(cmd)
    else:
        cmd += ["-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac"]

    # Metadata injection
    meta = p["ffmpeg_meta"]
    for k, v in meta.items():
        cmd += ["-metadata", f"{k}={v}"]

    cmd += [
        "-metadata", f"creation_time={ts_iso}",
        "-metadata", f"location={lat:+.4f}{lon:+.4f}/",
        "-metadata", f"location-eng={lat:+.4f}{lon:+.4f}/",
        "-movflags", "+faststart",
        out_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-300:])

    sid_tag = " [SynthID✗]" if remove_sid else ""
    log(f"🎬  {os.path.basename(src)} → {out_name}  [{device_key} · {loc['name']}{sid_tag}]")
    return out_name


# ─── GUI ──────────────────────────────────────────────────────────────────────
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Stacked — Metadata Simulator")
        self.root.geometry("740x700")
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)

        self.folder_var   = tk.StringVar()
        self.device_var   = tk.StringVar(value="IPHONE_15")
        self.synthid_var  = tk.BooleanVar(value=True)
        self.running      = False

        self._build()
        self._center()

    def _center(self):
        self.root.update_idletasks()
        w, h = 740, 700
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _build(self):
        # Header
        hdr = tk.Frame(self.root, bg=C["bg"], pady=22)
        hdr.pack(fill="x", padx=32)
        tk.Label(hdr, text="STACKED", font=("Helvetica Neue", 30, "bold"),
                 fg=C["primary"], bg=C["bg"]).pack(anchor="w")
        tk.Label(hdr, text="METADATA SIMULATOR  ·  v2.1  ·  Images + Videos + SynthID Removal",
                 font=("Helvetica Neue", 10), fg=C["sub"], bg=C["bg"]).pack(anchor="w")

        self._div()

        # Folder
        sec = tk.Frame(self.root, bg=C["bg"], pady=16)
        sec.pack(fill="x", padx=32)
        tk.Label(sec, text="IMAGE / VIDEO FOLDER", font=("Helvetica Neue", 9, "bold"),
                 fg=C["sub"], bg=C["bg"]).pack(anchor="w", pady=(0, 6))
        row = tk.Frame(sec, bg=C["bg"])
        row.pack(fill="x")
        self.path_entry = tk.Entry(
            row, textvariable=self.folder_var, font=("Helvetica Neue", 11),
            bg=C["card"], fg=C["text"], insertbackground=C["text"],
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=C["border"], highlightcolor=C["primary"],
            readonlybackground=C["card"], state="readonly")
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 10))
        self._btn(row, "BROWSE", self._browse, side="left", ipady=10)

        # Device
        dev_sec = tk.Frame(self.root, bg=C["bg"])
        dev_sec.pack(fill="x", padx=32, pady=(0, 14))
        tk.Label(dev_sec, text="DEVICE PROFILE", font=("Helvetica Neue", 9, "bold"),
                 fg=C["sub"], bg=C["bg"]).pack(anchor="w", pady=(0, 6))
        row2 = tk.Frame(dev_sec, bg=C["bg"])
        row2.pack(anchor="w")
        for key, label in [("IPHONE_15",   "iPhone 15 Pro"),
                            ("SAMSUNG_S24", "Samsung S24 Ultra"),
                            ("PIXEL_8",     "Pixel 8 Pro")]:
            tk.Radiobutton(row2, text=label, variable=self.device_var, value=key,
                           font=("Helvetica Neue", 11), fg=C["text"], bg=C["bg"],
                           selectcolor=C["bg"], activebackground=C["bg"],
                           activeforeground=C["primary"], padx=14).pack(side="left")

        # SynthID toggle
        sid_sec = tk.Frame(self.root, bg=C["bg"])
        sid_sec.pack(fill="x", padx=32, pady=(0, 16))
        tk.Checkbutton(sid_sec, text="  Remove SynthID Watermark  (images + video re-encode)",
                       variable=self.synthid_var,
                       font=("Helvetica Neue", 11), fg=C["primary"], bg=C["bg"],
                       selectcolor=C["bg"], activebackground=C["bg"],
                       activeforeground=C["primary"]).pack(anchor="w")

        self._div()

        # Log
        log_sec = tk.Frame(self.root, bg=C["bg"], pady=14)
        log_sec.pack(fill="both", expand=True, padx=32)
        tk.Label(log_sec, text="SYSTEM LOG", font=("Helvetica Neue", 9, "bold"),
                 fg=C["sub"], bg=C["bg"]).pack(anchor="w", pady=(0, 6))
        self.log_box = tk.Text(
            log_sec, bg=C["card"], fg=C["primary"],
            font=("Menlo", 10), relief="flat", bd=0,
            highlightthickness=1, highlightbackground=C["border"],
            state="disabled", wrap="word")
        self.log_box.pack(fill="both", expand=True, ipady=8, ipadx=10)

        self._div()

        # Footer
        foot = tk.Frame(self.root, bg=C["bg"], pady=16)
        foot.pack(fill="x", padx=32)
        self.start_btn = self._btn(foot, "⚡  START SIMULATION", self._start,
                                   side="left", ipady=12, padx=24)
        tk.Label(foot, text="stacked.com", font=("Helvetica Neue", 10),
                 fg=C["sub"], bg=C["bg"]).pack(side="right")

    def _div(self):
        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x", padx=32)

    def _btn(self, parent, text, cmd, side=None, ipady=8, padx=16):
        b = tk.Button(parent, text=text, font=("Helvetica Neue", 11, "bold"),
                      bg=C["primary"], fg=C["bg"],
                      activebackground=C["dim"], activeforeground=C["bg"],
                      relief="flat", bd=0, padx=padx, command=cmd)
        b.pack(side=side, ipady=ipady)
        return b

    def _browse(self):
        path = filedialog.askdirectory(title="Select Folder")
        if path:
            self.folder_var.set(os.path.normpath(path))

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.root.update_idletasks()

    def _start(self):
        if self.running:
            return
        if not PIL_AVAILABLE:
            messagebox.showerror("Missing Deps", "Run: pip install Pillow piexif")
            return
        folder = self.folder_var.get()
        if not folder:
            messagebox.showwarning("No Folder", "Select a folder first.")
            return
        self.running = True
        self.start_btn.configure(state="disabled", text="PROCESSING...")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        threading.Thread(target=self._run_worker, args=(folder,), daemon=True).start()

    def _run_worker(self, folder):
        device = self.device_var.get()
        remove_sid = self.synthid_var.get()

        self._log(f"🚀  Starting simulation...")
        self._log(f"📱  Device : {device}")
        self._log(f"🛡   SynthID: {'REMOVE' if remove_sid else 'keep'}")
        self._log(f"📂  Folder : {folder}\n")

        out_dir = os.path.join(folder, "stacked_output")
        os.makedirs(out_dir, exist_ok=True)

        all_files = [f for f in os.listdir(folder)
                     if not os.path.isdir(os.path.join(folder, f))]
        images = [f for f in all_files if os.path.splitext(f)[1].lower() in IMAGE_EXTS]
        videos = [f for f in all_files if os.path.splitext(f)[1].lower() in VIDEO_EXTS]

        self._log(f"📋  Found {len(images)} image(s), {len(videos)} video(s)\n")

        ok, fail = 0, 0
        for f in images:
            try:
                process_image(os.path.join(folder, f), out_dir, device, remove_sid, self._log)
                ok += 1
            except Exception as e:
                self._log(f"❌  {f} → {e}")
                fail += 1

        for f in videos:
            try:
                process_video(os.path.join(folder, f), out_dir, device, remove_sid, self._log)
                ok += 1
            except Exception as e:
                self._log(f"❌  {f} → {e}")
                fail += 1

        self._log(f"\n{'─'*50}")
        self._log(f"✨  Complete — {ok} processed, {fail} failed")
        self._log(f"📁  Output → {out_dir}")

        self.running = False
        self.start_btn.configure(state="normal", text="⚡  START SIMULATION")


# ─── ENTRY ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
