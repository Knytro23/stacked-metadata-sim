"""
Stacked Metadata Simulator v2.2
Branding: stacked.com — dark charcoal, white, Owners font
"""
import tkinter as tk
from tkinter import filedialog, messagebox
import os, sys, string, random, datetime, subprocess, threading, shutil, platform

try:
    from PIL import Image, ImageFilter, ImageTk
    import piexif
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ─── STACKED BRAND (matches stacked.com exactly) ──────────────────────────────
C = {
    "bg":        "#111111",   # page background
    "surface":   "#1A1A1A",   # cards / inputs
    "surface2":  "#222222",   # slightly raised
    "border":    "#2A2A2A",   # dividers
    "text":      "#FFFFFF",   # primary text
    "sub":       "#888888",   # muted text
    "btn_pri":   "#FFFFFF",   # primary button bg (white)
    "btn_pri_fg":"#000000",   # primary button text
    "btn_sec":   "#252525",   # secondary button bg
    "btn_sec_fg":"#FFFFFF",   # secondary button text
    "hover_pri": "#E0E0E0",   # primary button hover
    "hover_sec": "#333333",   # secondary button hover
}

# ─── FONT HELPER ──────────────────────────────────────────────────────────────
def _get_font_dir():
    """Returns directory next to the executable (or script)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _install_owners_fonts():
    """
    Install Owners font files to user font directory so Tkinter can use them.
    macOS: ~/Library/Fonts/   Windows: %LOCALAPPDATA%\\Microsoft\\Windows\\Fonts\\
    No admin rights needed.
    """
    font_dir = _get_font_dir()
    fonts = {
        "Owners-Bold.otf":    "Owners-Bold.otf",
        "Owners-Regular.otf": "Owners-Regular.otf",
        "Owners-XBlack.otf":  "Owners-XBlack.otf",
    }
    system = platform.system()
    if system == "Darwin":
        dest = os.path.expanduser("~/Library/Fonts")
    elif system == "Windows":
        dest = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")
    else:
        dest = os.path.expanduser("~/.fonts")

    os.makedirs(dest, exist_ok=True)
    for src_name, dst_name in fonts.items():
        src = os.path.join(font_dir, src_name)
        dst = os.path.join(dest, dst_name)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)

    # On Windows, also notify the font subsystem
    if system == "Windows":
        try:
            import ctypes
            ctypes.windll.gdi32.AddFontResourceExW(
                os.path.join(dest, "Owners-Bold.otf"), 0x10, 0)
        except Exception:
            pass

# ─── DEVICE PROFILES ──────────────────────────────────────────────────────────
DEVICE_PROFILES = {
    "IPHONE_15": {
        "label": "iPhone 15 Pro",
        "Make": "Apple", "Model": "iPhone 15 Pro",
        "Software": "17.2.1", "LensMake": "Apple",
        "LensModel": "iPhone 15 Pro back triple camera 6.765mm f/1.78",
        "FocalLength": (677, 100), "FNumber": (178, 100),
        "ExposureTime": (1, 1000), "ISOSpeedRatings": 50,
        "Flash": 24, "WhiteBalance": 0, "ColorSpace": 1,
        "ExifVersion": b"0232", "FlashPixVersion": b"0100",
        "ffmeta": {"make": "Apple", "model": "iPhone 15 Pro",
                   "com.apple.quicktime.make": "Apple",
                   "com.apple.quicktime.model": "iPhone 15 Pro",
                   "com.apple.quicktime.software": "17.2.1"},
    },
    "SAMSUNG_S24": {
        "label": "Samsung S24 Ultra",
        "Make": "samsung", "Model": "SM-S928B",
        "Software": "S928BXXU2AXCA", "LensMake": "Samsung",
        "LensModel": "Samsung Galaxy S24 Ultra rear camera 6.3mm f/1.7",
        "FocalLength": (630, 100), "FNumber": (170, 100),
        "ExposureTime": (1, 1200), "ISOSpeedRatings": 64,
        "Flash": 0, "WhiteBalance": 0, "ColorSpace": 1,
        "ExifVersion": b"0220", "FlashPixVersion": b"0100",
        "ffmeta": {"make": "samsung", "model": "SM-S928B"},
    },
    "PIXEL_8": {
        "label": "Pixel 8 Pro",
        "Make": "Google", "Model": "Pixel 8 Pro",
        "Software": "HDR+ 1.0.560250830z", "LensMake": "Google",
        "LensModel": "Pixel 8 Pro back camera 6.81mm f/1.68",
        "FocalLength": (681, 100), "FNumber": (168, 100),
        "ExposureTime": (1, 800), "ISOSpeedRatings": 80,
        "Flash": 0, "WhiteBalance": 0, "ColorSpace": 1,
        "ExifVersion": b"0231", "FlashPixVersion": b"0100",
        "ffmeta": {"make": "Google", "model": "Pixel 8 Pro"},
    },
}

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


def dms(deg):
    d = int(abs(deg))
    mf = (abs(deg) - d) * 60
    m = int(mf)
    s = round((mf - m) * 60 * 100)
    return ((d, 1), (m, 1), (s, 100))

def rand_loc(): return random.choice(LOCATIONS)
def rand_ts(): return (datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 730))).strftime("%Y:%m:%d %H:%M:%S")
def rand_ts_iso(): return (datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 730))).strftime("%Y-%m-%dT%H:%M:%S")
def rand_fname(ext): return "IMG_" + "".join(random.choices(string.digits, k=8)) + ext


def remove_synthid(img):
    w, h = img.size
    img = img.resize((int(w * 0.997), int(h * 0.997)), Image.LANCZOS)
    img = img.resize((w, h), Image.LANCZOS)
    img = img.filter(ImageFilter.SMOOTH_MORE)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def process_image(src, out_dir, device_key, sid, log):
    p = DEVICE_PROFILES[device_key]
    ts, loc = rand_ts(), rand_loc()
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
    img = Image.open(src).convert("RGB")
    if sid: img = remove_synthid(img)
    out = os.path.join(out_dir, rand_fname(".jpg"))
    img.save(out, "JPEG", exif=piexif.dump(exif), quality=95)
    log(f"  ✓  {os.path.basename(src)}  →  {os.path.basename(out)}  [{p['label']} · {loc['name']}{'  ·  SynthID ✗' if sid else ''}]")


def process_video(src, out_dir, device_key, sid, log):
    p = DEVICE_PROFILES[device_key]
    ts_iso, loc = rand_ts_iso(), rand_loc()
    lat, lon = loc["lat"], loc["lon"]
    out = os.path.join(out_dir, rand_fname(".mp4"))
    cmd = ["ffmpeg", "-y", "-i", src]
    if sid:
        cmd += ["-vf", "scale=iw*0.997:ih*0.997,scale=iw/0.997:ih/0.997,unsharp=3:3:0.3",
                "-c:v", "libx264", "-crf", str(random.randint(19, 22)), "-preset", "slow",
                "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac"]
    for k, v in p["ffmeta"].items():
        cmd += ["-metadata", f"{k}={v}"]
    cmd += ["-metadata", f"creation_time={ts_iso}",
            "-metadata", f"location={lat:+.4f}{lon:+.4f}/",
            "-movflags", "+faststart", out]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0: raise RuntimeError(res.stderr[-200:])
    log(f"  ✓  {os.path.basename(src)}  →  {os.path.basename(out)}  [{p['label']} · {loc['name']}{'  ·  SynthID ✗' if sid else ''}]")


# ─── GUI ──────────────────────────────────────────────────────────────────────
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Stacked — Metadata Simulator")
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)

        self.folder_var  = tk.StringVar()
        self.device_var  = tk.StringVar(value="IPHONE_15")
        self.synthid_var = tk.BooleanVar(value=True)
        self.running     = False
        self._logo_img   = None

        # Install and resolve Owners font
        _install_owners_fonts()
        self._f_hero    = ("Owners TRIAL XXWide XBlack", 28)
        self._f_nav     = ("Owners TRIAL XXWide", 13)
        self._f_label   = ("Owners TRIAL XXWide", 9, "bold")
        self._f_body    = ("Helvetica Neue", 11)
        self._f_sub     = ("Helvetica Neue", 10)
        self._f_log     = ("Menlo", 10)
        self._f_btn     = ("Owners TRIAL XXWide", 11)

        self._build()
        self._center(760, 740)

    def _center(self, w, h):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ── widgets ───────────────────────────────────────────────────────────────
    def _build(self):
        # Navbar strip
        nav = tk.Frame(self.root, bg=C["bg"], height=56)
        nav.pack(fill="x")
        nav.pack_propagate(False)

        # Logo — try PNG first
        logo_path = os.path.join(_get_font_dir(), "stacked_logo.png")
        if os.path.exists(logo_path) and PIL_AVAILABLE:
            try:
                raw = Image.open(logo_path).convert("RGBA")
                ratio = raw.width / raw.height
                lh = 28
                raw = raw.resize((int(lh * ratio), lh), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(raw)
                tk.Label(nav, image=self._logo_img, bg=C["bg"]).pack(
                    side="left", padx=28, pady=14)
            except Exception:
                self._text_logo(nav)
        else:
            self._text_logo(nav)

        tk.Label(nav, text="Metadata Simulator", font=self._f_nav,
                 fg=C["sub"], bg=C["bg"]).pack(side="left", pady=18)

        # Top divider
        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x")

        # ── Hero ──────────────────────────────────────────────────────────────
        hero = tk.Frame(self.root, bg=C["bg"], pady=28)
        hero.pack(fill="x", padx=36)
        tk.Label(hero,
                 text="Inject. Spoof. Ship.",
                 font=self._f_hero,
                 fg=C["text"], bg=C["bg"],
                 justify="left").pack(anchor="w")
        tk.Label(hero,
                 text="Batch metadata injection for images & videos. SynthID removal included.",
                 font=self._f_sub,
                 fg=C["sub"], bg=C["bg"],
                 justify="left").pack(anchor="w", pady=(4, 0))

        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x", padx=36)

        # ── Folder picker ─────────────────────────────────────────────────────
        sec = tk.Frame(self.root, bg=C["bg"], pady=20)
        sec.pack(fill="x", padx=36)
        tk.Label(sec, text="FOLDER", font=self._f_label,
                 fg=C["sub"], bg=C["bg"]).pack(anchor="w", pady=(0, 6))
        row = tk.Frame(sec, bg=C["bg"])
        row.pack(fill="x")
        self.path_entry = tk.Entry(
            row, textvariable=self.folder_var,
            font=self._f_body,
            bg=C["surface"], fg=C["text"],
            insertbackground=C["text"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=C["border"],
            highlightcolor=C["text"],
            readonlybackground=C["surface"],
            state="readonly")
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=11, padx=(0, 10))
        self._pri_btn(row, "Browse", self._browse, side="left")

        # ── Device selector ───────────────────────────────────────────────────
        dev_sec = tk.Frame(self.root, bg=C["bg"])
        dev_sec.pack(fill="x", padx=36, pady=(0, 16))
        tk.Label(dev_sec, text="DEVICE PROFILE", font=self._f_label,
                 fg=C["sub"], bg=C["bg"]).pack(anchor="w", pady=(0, 8))
        btn_row = tk.Frame(dev_sec, bg=C["bg"])
        btn_row.pack(anchor="w")
        for key, lbl in [("IPHONE_15",   "iPhone 15 Pro"),
                          ("SAMSUNG_S24", "Samsung S24 Ultra"),
                          ("PIXEL_8",     "Pixel 8 Pro")]:
            self._device_pill(btn_row, key, lbl)

        # ── SynthID toggle ────────────────────────────────────────────────────
        sid_sec = tk.Frame(self.root, bg=C["bg"])
        sid_sec.pack(fill="x", padx=36, pady=(0, 16))
        tk.Checkbutton(
            sid_sec,
            text="  Remove SynthID Watermark",
            variable=self.synthid_var,
            font=self._f_body,
            fg=C["text"], bg=C["bg"],
            selectcolor=C["surface"],
            activebackground=C["bg"],
            activeforeground=C["text"]).pack(anchor="w")
        tk.Label(sid_sec,
                 text="  Applies frequency-domain perturbation to images; re-encodes video with perturbed codec params.",
                 font=self._f_sub,
                 fg=C["sub"], bg=C["bg"],
                 wraplength=660, justify="left").pack(anchor="w", pady=(2, 0))

        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x", padx=36)

        # ── Log ───────────────────────────────────────────────────────────────
        log_sec = tk.Frame(self.root, bg=C["bg"], pady=16)
        log_sec.pack(fill="both", expand=True, padx=36)
        tk.Label(log_sec, text="OUTPUT LOG", font=self._f_label,
                 fg=C["sub"], bg=C["bg"]).pack(anchor="w", pady=(0, 6))
        self.log_box = tk.Text(
            log_sec,
            bg=C["surface"], fg="#CCCCCC",
            font=self._f_log,
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=C["border"],
            state="disabled", wrap="word",
            cursor="arrow")
        self.log_box.pack(fill="both", expand=True, ipady=10, ipadx=12)

        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x", padx=36)

        # ── Footer ────────────────────────────────────────────────────────────
        foot = tk.Frame(self.root, bg=C["bg"], pady=18)
        foot.pack(fill="x", padx=36)
        self.start_btn = self._pri_btn(foot, "Start Simulation  →", self._start, side="left")
        tk.Label(foot, text="© Stacked · stacked.com",
                 font=self._f_sub,
                 fg=C["sub"], bg=C["bg"]).pack(side="right")

    def _text_logo(self, parent):
        tk.Label(parent, text="✦ Stacked",
                 font=("Owners TRIAL XXWide XBlack", 16),
                 fg=C["text"], bg=C["bg"]).pack(side="left", padx=28, pady=14)

    def _pri_btn(self, parent, text, cmd, side=None):
        b = tk.Button(parent, text=text,
                      font=self._f_btn,
                      bg=C["btn_pri"], fg=C["btn_pri_fg"],
                      activebackground=C["hover_pri"],
                      activeforeground=C["btn_pri_fg"],
                      relief="flat", bd=0, padx=20,
                      cursor="hand2", command=cmd)
        b.pack(side=side, ipady=11)
        return b

    def _sec_btn(self, parent, text, cmd, side=None):
        b = tk.Button(parent, text=text,
                      font=self._f_body,
                      bg=C["btn_sec"], fg=C["btn_sec_fg"],
                      activebackground=C["hover_sec"],
                      activeforeground=C["btn_sec_fg"],
                      relief="flat", bd=0, padx=20,
                      cursor="hand2", command=cmd)
        b.pack(side=side, ipady=11)
        return b

    def _device_pill(self, parent, key, label):
        """Radio-style pill buttons matching the stacked.com secondary button style."""
        def select():
            self.device_var.set(key)
            self._refresh_pills()
        btn = tk.Button(parent, text=label,
                        font=self._f_body,
                        relief="flat", bd=0, padx=16,
                        cursor="hand2", command=select)
        btn.pack(side="left", ipady=8, padx=(0, 8))
        self._pill_btns = getattr(self, "_pill_btns", {})
        self._pill_btns[key] = btn
        self._refresh_pills()

    def _refresh_pills(self):
        sel = self.device_var.get()
        for k, b in getattr(self, "_pill_btns", {}).items():
            if k == sel:
                b.configure(bg=C["btn_pri"], fg=C["btn_pri_fg"])
            else:
                b.configure(bg=C["btn_sec"], fg=C["btn_sec_fg"])

    def _browse(self):
        path = filedialog.askdirectory(title="Select Image / Video Folder")
        if path:
            self.folder_var.set(os.path.normpath(path))

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.root.update_idletasks()

    def _start(self):
        if self.running: return
        if not PIL_AVAILABLE:
            messagebox.showerror("Missing Dependencies",
                "Run: pip install Pillow piexif")
            return
        folder = self.folder_var.get()
        if not folder:
            messagebox.showwarning("No Folder Selected",
                "Please browse to a folder containing images or videos.")
            return
        self.running = True
        self.start_btn.configure(state="disabled", text="Processing…")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        threading.Thread(target=self._worker, args=(folder,), daemon=True).start()

    def _worker(self, folder):
        device  = self.device_var.get()
        sid     = self.synthid_var.get()

        self._log(f"Starting  ·  Device: {DEVICE_PROFILES[device]['label']}  ·  SynthID removal: {'on' if sid else 'off'}\n")

        out_dir = os.path.join(folder, "stacked_output")
        os.makedirs(out_dir, exist_ok=True)

        files = [f for f in os.listdir(folder)
                 if not os.path.isdir(os.path.join(folder, f))]
        images = [f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTS]
        videos = [f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXTS]

        self._log(f"{len(images)} image(s)  ·  {len(videos)} video(s)\n")

        ok = fail = 0
        for f in images:
            try:
                process_image(os.path.join(folder, f), out_dir, device, sid, self._log)
                ok += 1
            except Exception as e:
                self._log(f"  ✗  {f}  →  {e}")
                fail += 1
        for f in videos:
            try:
                process_video(os.path.join(folder, f), out_dir, device, sid, self._log)
                ok += 1
            except Exception as e:
                self._log(f"  ✗  {f}  →  {e}")
                fail += 1

        self._log(f"\n{'─'*52}")
        self._log(f"Done  ·  {ok} processed  ·  {fail} failed")
        self._log(f"Output  →  {out_dir}")

        self.running = False
        self.start_btn.configure(state="normal", text="Start Simulation  →")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
