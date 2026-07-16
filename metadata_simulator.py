"""
Meta Data Simulator v2.4

The processing functions in this module are shared by the desktop GUI and the
all-in-one web service. Tkinter is optional so the server/container can import
the media-processing code in headless environments.
"""
import os, sys, string, random, datetime, subprocess, threading, shutil, platform

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    TK_AVAILABLE = True
except ImportError:
    tk = None
    filedialog = None
    messagebox = None
    TK_AVAILABLE = False

try:
    from PIL import Image, ImageFilter
    if TK_AVAILABLE:
        from PIL import ImageTk
    else:
        ImageTk = None
    import piexif
    PIL_AVAILABLE = True
except ImportError:
    ImageTk = None
    PIL_AVAILABLE = False

# HEIC is the default iPhone capture format; register the opener when available
# so .heic inputs decode (output is always re-encoded JPEG regardless).
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# ─── BRAND COLORS ─────────────────────────────────────────────────────────────
C = {
    "bg":      "#111111",
    "surface": "#1A1A1A",
    "border":  "#2A2A2A",
    "text":    "#FFFFFF",
    "sub":     "#888888",
    "pri_bg":  "#FFFFFF",
    "pri_fg":  "#000000",
    "sec_bg":  "#252525",
    "sec_fg":  "#FFFFFF",
}

# ─── DEVICE PROFILES ──────────────────────────────────────────────────────────
# Each post is spoofed to match the device it is dispatched to. iOS software
# strings vary slightly per device so a fleet of identical builds is itself not a
# fingerprint; iOS_POOL supplies a small realistic spread picked per file.
# CALIBRATION: the ground-truth values (LensModel text, FocalLength, FNumber,
# ExifVersion) should be validated against a real photo pulled off a fleet device
# — see calibrate_from_exif(). Values below are best-known defaults.
PROFILES = {
    "IPHONE_15":     {"label": "iPhone 15",         "Make": "Apple",    "Model": "iPhone 15",         "iOS_POOL": ["17.5.1","17.6.1","18.1.1","18.2.1"], "LensMake": "Apple",    "LensModel": "iPhone 15 back dual camera 6.86mm f/1.6",   "FocalLength": (686,100), "FNumber": (160,100), "ExposureTime": (1,1000), "ISO": 64,  "Flash": 24, "WB": 0, "CS": 1, "EV": b"0232", "FPV": b"0100", "ffmeta_model": "iPhone 15"},
    "IPHONE_15_PRO": {"label": "iPhone 15 Pro",     "Make": "Apple",    "Model": "iPhone 15 Pro",     "iOS_POOL": ["17.5.1","17.6.1","18.1.1","18.2.1"], "LensMake": "Apple",    "LensModel": "iPhone 15 Pro back triple camera 6.765mm f/1.78", "FocalLength": (677,100), "FNumber": (178,100), "ExposureTime": (1,1000), "ISO": 50, "Flash": 24, "WB": 0, "CS": 1, "EV": b"0232", "FPV": b"0100", "ffmeta_model": "iPhone 15 Pro"},
    "IPHONE_14":     {"label": "iPhone 14",         "Make": "Apple",    "Model": "iPhone 14",         "iOS_POOL": ["16.6.1","17.5.1","17.6.1","18.1.1"], "LensMake": "Apple",    "LensModel": "iPhone 14 back dual camera 5.7mm f/1.5",  "FocalLength": (570,100), "FNumber": (150,100), "ExposureTime": (1,900),  "ISO": 64,  "Flash": 24, "WB": 0, "CS": 1, "EV": b"0232", "FPV": b"0100", "ffmeta_model": "iPhone 14"},
    "PIXEL_8":       {"label": "Pixel 8",           "Make": "Google",   "Model": "Pixel 8",           "iOS_POOL": ["HDR+ 1.0.680000000","HDR+ 1.0.690000000"], "LensMake": "Google", "LensModel": "Pixel 8 back camera 6.9mm f/1.68",       "FocalLength": (690,100), "FNumber": (168,100), "ExposureTime": (1,800),  "ISO": 80,  "Flash": 0, "WB": 0, "CS": 1, "EV": b"0231", "FPV": b"0100", "ffmeta_model": "Pixel 8"},
}

# Maps whatever model string the swarm device carries (raw identifier like
# "iphone15,4", friendly name like "iPhone 15 Pro", or an Android model) to a
# profile key. Unknown iPhones fall back to IPHONE_15, unknown Androids to PIXEL_8.
DEVICE_MODEL_MAP = {
    "iphone15,4": "IPHONE_15", "iphone15,5": "IPHONE_15",
    "iphone16,1": "IPHONE_15_PRO", "iphone16,2": "IPHONE_15_PRO",
    "iphone14,7": "IPHONE_14", "iphone14,8": "IPHONE_14",
    "iphone 15": "IPHONE_15", "iphone 15 plus": "IPHONE_15",
    "iphone 15 pro": "IPHONE_15_PRO", "iphone 15 pro max": "IPHONE_15_PRO",
    "iphone 14": "IPHONE_14", "iphone 14 plus": "IPHONE_14",
    "pixel 8": "PIXEL_8", "pixel 8 pro": "PIXEL_8",
}
DEFAULT_PROFILE = "IPHONE_15"


def resolve_profile(device_model):
    """Pick a profile key for a swarm device's model string (see DEVICE_MODEL_MAP)."""
    if not device_model:
        return DEFAULT_PROFILE
    key = str(device_model).strip().lower()
    if key.upper() in PROFILES:
        return key.upper()
    if key in DEVICE_MODEL_MAP:
        return DEVICE_MODEL_MAP[key]
    if "iphone" in key:
        return "IPHONE_15_PRO" if "pro" in key else "IPHONE_15"
    if "pixel" in key or "android" in key or "sm-" in key or "moto" in key:
        return "PIXEL_8"
    return DEFAULT_PROFILE


# US-only locations for a US-audience fleet. Each is a metro center; every file
# gets a small random offset (JITTER_DEG, ~a few km) so no two posts of the same
# source image ever carry the identical GPS point.
LOCATIONS = [
    {"name": "Los Angeles",     "lat": 34.0522, "lon": -118.2437},
    {"name": "Birmingham, AL",  "lat": 33.5186, "lon":  -86.8104},
    {"name": "New York City",   "lat": 40.7128, "lon":  -74.0060},
    {"name": "Miami",           "lat": 25.7617, "lon":  -80.1918},
]
JITTER_DEG = 0.045  # ~5 km at these latitudes

IMAGE_EXTS = {".jpg",".jpeg",".tiff",".tif",".png",".webp",".heic"}
VIDEO_EXTS = {".mp4",".mov",".avi",".mkv",".m4v",".3gp"}


def _res(name):
    """Path to bundled resource (works frozen + dev)."""
    if getattr(sys, 'frozen', False):
        # PyInstaller one-file: resources extract to sys._MEIPASS temp dir
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, name)

def _install_fonts():
    system = platform.system()
    dest = (os.path.expanduser("~/Library/Fonts") if system=="Darwin"
            else os.path.join(os.environ.get("LOCALAPPDATA",""), "Microsoft","Windows","Fonts") if system=="Windows"
            else os.path.expanduser("~/.fonts"))
    os.makedirs(dest, exist_ok=True)
    for f in ["Owners-Bold.otf","Owners-Regular.otf","Owners-XBlack.otf"]:
        src = _res(f)
        dst = os.path.join(dest, f)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
    if system == "Windows":
        try:
            import ctypes
            ctypes.windll.gdi32.AddFontResourceExW(
                os.path.join(dest,"Owners-Bold.otf"), 0x10, 0)
        except Exception:
            pass

def _dms(d):
    deg=int(abs(d)); mf=(abs(d)-deg)*60; m=int(mf); s=round((mf-m)*60*100)
    return ((deg,1),(m,1),(s,100))

def _jittered_loc(randomize=True):
    """A US metro, offset by a small random amount so no two posts share a point."""
    loc = random.choice(LOCATIONS) if randomize else LOCATIONS[0]
    return {
        "name": loc["name"],
        "lat": loc["lat"] + random.uniform(-JITTER_DEG, JITTER_DEG),
        "lon": loc["lon"] + random.uniform(-JITTER_DEG, JITTER_DEG),
        "alt": round(random.uniform(2, 180), 1),
    }

def _rand_dt():  return datetime.datetime.now()-datetime.timedelta(days=random.randint(1,120),seconds=random.randint(0,86399))
def _rand_fn(ext): return "IMG_"+"".join(random.choices(string.digits,k=4))+"".join(random.choices(string.ascii_uppercase,k=4))+ext

def _iso_software(p):
    return random.choice(p.get("iOS_POOL") or [p.get("Software","")])

def _gps_block(loc, dt):
    """Full GPS IFD an iPhone actually writes: lat/lon + ref, altitude, and a
    timestamp coherent with the capture time."""
    lat, lon, alt = loc["lat"], loc["lon"], loc["alt"]
    return {
        piexif.GPSIFD.GPSLatitudeRef: b"N" if lat>=0 else b"S",
        piexif.GPSIFD.GPSLatitude: _dms(lat),
        piexif.GPSIFD.GPSLongitudeRef: b"E" if lon>=0 else b"W",
        piexif.GPSIFD.GPSLongitude: _dms(lon),
        piexif.GPSIFD.GPSAltitudeRef: 0,
        piexif.GPSIFD.GPSAltitude: (int(round(alt*100)), 100),
        piexif.GPSIFD.GPSHPositioningError: (random.randint(3,12), 1),
        piexif.GPSIFD.GPSDateStamp: dt.strftime("%Y:%m:%d").encode(),
        piexif.GPSIFD.GPSTimeStamp: ((dt.hour,1),(dt.minute,1),(dt.second,1)),
    }

def _synthid_strip(img):
    """Pixel-domain mitigation for invisible watermarks (Google SynthID and
    similar): a sub-pixel resize round-trip + smooth/sharpen + faint noise
    perturbs the high-frequency signal these watermarks ride on. This degrades
    them and, combined with JPEG re-encoding, is not a cryptographic removal
    guarantee — the metadata-level AI markers ARE fully stripped (see below)."""
    w,h=img.size
    img=img.resize((int(w*.995),int(h*.995)),Image.LANCZOS).resize((w,h),Image.LANCZOS)
    img=img.filter(ImageFilter.SMOOTH_MORE).filter(ImageFilter.SHARPEN)
    px=img.load()
    for _ in range(int(w*h*0.02)):  # sparse ±1 dither over ~2% of pixels
        x=random.randrange(w); y=random.randrange(h); r,g,b=px[x,y]
        d=random.choice((-1,1))
        px[x,y]=(max(0,min(255,r+d)),max(0,min(255,g+d)),max(0,min(255,b+d)))
    return img

def process_image(src, out_dir, key, sid, log, randomize_location=True):
    p=PROFILES[key]; dt=_rand_dt(); ts=dt.strftime("%Y:%m:%d %H:%M:%S")
    loc=_jittered_loc(randomize_location); sw=_iso_software(p)
    # Rebuilt from scratch, so ALL original EXIF/XMP/C2PA AI provenance is dropped.
    exif={"0th":{piexif.ImageIFD.Make:p["Make"].encode(),piexif.ImageIFD.Model:p["Model"].encode(),piexif.ImageIFD.Software:sw.encode(),piexif.ImageIFD.DateTime:ts.encode()},
          "Exif":{piexif.ExifIFD.DateTimeOriginal:ts.encode(),piexif.ExifIFD.DateTimeDigitized:ts.encode(),piexif.ExifIFD.LensMake:p["LensMake"].encode(),piexif.ExifIFD.LensModel:p["LensModel"].encode(),piexif.ExifIFD.FocalLength:p["FocalLength"],piexif.ExifIFD.FNumber:p["FNumber"],piexif.ExifIFD.ExposureTime:p["ExposureTime"],piexif.ExifIFD.ISOSpeedRatings:p["ISO"],piexif.ExifIFD.Flash:p["Flash"],piexif.ExifIFD.WhiteBalance:p["WB"],piexif.ExifIFD.ColorSpace:p["CS"],piexif.ExifIFD.ExifVersion:p["EV"],piexif.ExifIFD.FlashpixVersion:p["FPV"]},
          "GPS":_gps_block(loc, dt),
          "1st":{},"thumbnail":None}
    img=Image.open(src).convert("RGB")
    if sid: img=_synthid_strip(img)
    out=os.path.join(out_dir,_rand_fn(".jpg"))
    # save without xmp=/icc_profile= so no source provenance sidecar rides along
    img.save(out,"JPEG",exif=piexif.dump(exif),quality=random.randint(93,96))
    log(f"  ✓  {os.path.basename(src)} → {os.path.basename(out)}  [{p['label']} · {loc['name']}{'  · SynthID✗' if sid else ''}]")
    return out

def process_video(src, out_dir, key, sid, log, randomize_location=True):
    p=PROFILES[key]; dt=_rand_dt(); ts=dt.strftime("%Y-%m-%dT%H:%M:%S")
    loc=_jittered_loc(randomize_location); lat,lon=loc["lat"],loc["lon"]
    out=os.path.join(out_dir,_rand_fn(".mp4"))
    # -map_metadata -1 drops ALL source container metadata (incl. AI/C2PA tags)
    # before we write our own.
    cmd=["ffmpeg","-y","-i",src,"-map_metadata","-1"]
    # trunc(.../2)*2 keeps every intermediate dimension even so libx264/yuv420p
    # accepts it (a raw 0.997 factor can yield odd dimensions and fail the encode).
    if sid: cmd+=["-vf","scale=trunc(iw*0.997/2)*2:trunc(ih*0.997/2)*2,scale=trunc(iw/0.997/2)*2:trunc(ih/0.997/2)*2,unsharp=3:3:0.3","-c:v","libx264","-crf",str(random.randint(19,22)),"-preset","slow","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k"]
    else:   cmd+=["-c:v","libx264","-crf","20","-preset","medium","-pix_fmt","yuv420p","-c:a","aac"]
    cmd+=["-metadata",f"make={p['Make']}","-metadata",f"model={p['ffmeta_model']}"]
    if p["Make"]=="Apple":
        cmd+=["-metadata",f"com.apple.quicktime.make={p['Make']}","-metadata",f"com.apple.quicktime.model={p['ffmeta_model']}","-metadata",f"com.apple.quicktime.software={_iso_software(p)}"]
    # use_metadata_tags is required for the com.apple.quicktime.* keys to persist
    # into the mov metadata atom instead of being dropped as non-standard.
    cmd+=["-metadata",f"creation_time={ts}","-metadata",f"location={lat:+.4f}{lon:+.4f}/","-metadata",f"com.apple.quicktime.location.ISO6709={lat:+.4f}{lon:+.4f}/","-movflags","use_metadata_tags+faststart",out]
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode!=0: raise RuntimeError(r.stderr[-200:])
    log(f"  ✓  {os.path.basename(src)} → {os.path.basename(out)}  [{p['label']} · {loc['name']}{'  · SynthID✗' if sid else ''}]")
    return out


def read_image_metadata(path):
    """Read back the spoof-relevant EXIF fields — used by the /verify self-check
    and the pipeline audit log to prove processing actually took effect."""
    exif = piexif.load(path)
    def s(ifd, tag):
        v = exif.get(ifd, {}).get(tag)
        return v.decode(errors="replace") if isinstance(v, bytes) else v
    return {
        "Make": s("0th", piexif.ImageIFD.Make),
        "Model": s("0th", piexif.ImageIFD.Model),
        "Software": s("0th", piexif.ImageIFD.Software),
        "DateTimeOriginal": s("Exif", piexif.ExifIFD.DateTimeOriginal),
        "LensModel": s("Exif", piexif.ExifIFD.LensModel),
        "GPSLatitude": exif.get("GPS", {}).get(piexif.GPSIFD.GPSLatitude),
        "GPSLongitude": exif.get("GPS", {}).get(piexif.GPSIFD.GPSLongitude),
        "GPSLatitudeRef": s("GPS", piexif.GPSIFD.GPSLatitudeRef),
    }


def verify_image_spoof(path, key):
    """True when the output metadata matches the requested profile and carries a
    US GPS point — the assertion behind the pipeline's fail-closed gate."""
    p = PROFILES[key]
    m = read_image_metadata(path)
    gps = m.get("GPSLatitude")
    lat = (gps[0][0]/gps[0][1] + gps[1][0]/gps[1][1]/60 + gps[2][0]/gps[2][1]/3600) if gps else None
    us_lat = lat is not None and 24.0 <= lat <= 49.5 and m.get("GPSLatitudeRef") == "N"
    return {
        "verified": m.get("Make") == p["Make"] and m.get("Model") == p["Model"] and us_lat,
        "metadata": m,
    }


# ─── GUI ──────────────────────────────────────────────────────────────────────
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Meta Data Simulator")
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)

        self.folder_var  = tk.StringVar()
        self.device_var  = tk.StringVar(value="IPHONE_15")
        self.synthid_var = tk.BooleanVar(value=True)
        self.location_var = tk.BooleanVar(value=True)
        self.running     = False
        self._logo_img   = None
        self._pill_refs  = {}

        _install_fonts()

        # Fonts — safe fallbacks if Owners not yet active in this session
        O  = "Owners TRIAL XXWide XBlack"
        OB = "Owners TRIAL XXWide"
        FB = "Helvetica Neue"
        self.F = {
            "hero":  (O,  26),
            "nav":   (OB, 12),
            "lbl":   (FB, 9,  "bold"),
            "body":  (FB, 11),
            "sub":   (FB, 10),
            "log":   ("Menlo", 10),
            "btn":   (OB, 11),
        }

        self._build()
        self._center(760, 720)

    def _center(self, w, h):
        self.root.update_idletasks()
        sw,sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _build(self):
        F = self.F

        # ── FOOTER packed first so it's always visible ────────────────────────
        tk.Frame(self.root, bg=C["border"], height=1).pack(side="bottom", fill="x")
        foot = tk.Frame(self.root, bg=C["bg"], pady=16)
        foot.pack(side="bottom", fill="x", padx=32)

        self.start_btn = tk.Button(
            foot, text="Start Simulation  →",
            font=F["btn"],
            bg=C["pri_bg"], fg=C["pri_fg"],
            activebackground="#E0E0E0", activeforeground="#000000",
            relief="flat", bd=0, padx=24, cursor="hand2",
            command=self._start)
        self.start_btn.pack(side="left", ipady=12)

        tk.Label(foot, text="© Meta Data Simulator",
                 font=F["sub"], fg=C["sub"], bg=C["bg"]).pack(side="right")

        # ── NAVBAR ────────────────────────────────────────────────────────────
        nav = tk.Frame(self.root, bg=C["bg"], height=54)
        nav.pack(side="top", fill="x")
        nav.pack_propagate(False)

        tk.Label(nav, text="✦ Meta Data Simulator", font=F["hero"], fg=C["text"], bg=C["bg"]).pack(side="left", padx=28, pady=12)

        tk.Frame(self.root, bg=C["border"], height=1).pack(side="top", fill="x")

        # ── HERO ──────────────────────────────────────────────────────────────
        hero = tk.Frame(self.root, bg=C["bg"], pady=22)
        hero.pack(side="top", fill="x", padx=32)
        tk.Label(hero, text="Inject. Spoof. Ship.", font=F["hero"], fg=C["text"], bg=C["bg"]).pack(anchor="w")
        tk.Label(hero, text="Batch EXIF injection for images & videos · SynthID removal included.",
                 font=F["sub"], fg=C["sub"], bg=C["bg"]).pack(anchor="w", pady=(3,0))

        tk.Frame(self.root, bg=C["border"], height=1).pack(side="top", fill="x", padx=32)

        # ── FOLDER ────────────────────────────────────────────────────────────
        sec = tk.Frame(self.root, bg=C["bg"], pady=18)
        sec.pack(side="top", fill="x", padx=32)
        tk.Label(sec, text="IMAGE / VIDEO FOLDER", font=F["lbl"], fg=C["sub"], bg=C["bg"]).pack(anchor="w", pady=(0,6))
        row = tk.Frame(sec, bg=C["bg"])
        row.pack(fill="x")
        tk.Entry(row, textvariable=self.folder_var, font=F["body"],
                 bg=C["surface"], fg=C["text"], insertbackground=C["text"],
                 relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=C["border"], highlightcolor=C["text"],
                 readonlybackground=C["surface"], state="readonly"
                 ).pack(side="left", fill="x", expand=True, ipady=11, padx=(0,10))
        tk.Button(row, text="Browse", font=F["body"],
                  bg=C["pri_bg"], fg=C["pri_fg"],
                  activebackground="#E0E0E0", activeforeground="#000000",
                  relief="flat", bd=0, padx=18, cursor="hand2",
                  command=self._browse).pack(side="left", ipady=11)

        # ── DEVICE ────────────────────────────────────────────────────────────
        dev = tk.Frame(self.root, bg=C["bg"])
        dev.pack(side="top", fill="x", padx=32, pady=(0,14))
        tk.Label(dev, text="DEVICE PROFILE", font=F["lbl"], fg=C["sub"], bg=C["bg"]).pack(anchor="w", pady=(0,8))
        pills = tk.Frame(dev, bg=C["bg"])
        pills.pack(anchor="w")
        for key in PROFILES:
            self._pill(pills, key)

        # ── SYNTHID ───────────────────────────────────────────────────────────
        sid = tk.Frame(self.root, bg=C["bg"])
        sid.pack(side="top", fill="x", padx=32, pady=(0,14))
        tk.Checkbutton(sid, text="  Remove SynthID Watermark",
                       variable=self.synthid_var, font=F["body"],
                       fg=C["text"], bg=C["bg"], selectcolor=C["surface"],
                       activebackground=C["bg"], activeforeground=C["text"]).pack(anchor="w")
        tk.Checkbutton(sid, text="  Randomize GPS Location",
                       variable=self.location_var, font=F["body"],
                       fg=C["text"], bg=C["bg"], selectcolor=C["surface"],
                       activebackground=C["bg"], activeforeground=C["text"]).pack(anchor="w", pady=(6,0))

        tk.Frame(self.root, bg=C["border"], height=1).pack(side="top", fill="x", padx=32)

        # ── LOG ───────────────────────────────────────────────────────────────
        log_sec = tk.Frame(self.root, bg=C["bg"], pady=14)
        log_sec.pack(side="top", fill="both", expand=True, padx=32)
        tk.Label(log_sec, text="OUTPUT LOG", font=F["lbl"], fg=C["sub"], bg=C["bg"]).pack(anchor="w", pady=(0,6))
        self.log_box = tk.Text(
            log_sec, bg=C["surface"], fg="#CCCCCC", font=F["log"],
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=C["border"], state="disabled",
            wrap="word", cursor="arrow")
        self.log_box.pack(fill="both", expand=True, ipady=10, ipadx=10)

    def _pill(self, parent, key):
        lbl = PROFILES[key]["label"]
        def select():
            self.device_var.set(key)
            self._refresh_pills()
        b = tk.Button(parent, text=lbl, font=self.F["body"],
                      relief="flat", bd=0, padx=16, cursor="hand2", command=select)
        b.pack(side="left", ipady=8, padx=(0,8))
        self._pill_refs[key] = b
        self._refresh_pills()

    def _refresh_pills(self):
        sel = self.device_var.get()
        for k, b in self._pill_refs.items():
            b.configure(bg=C["pri_bg"], fg=C["pri_fg"]) if k==sel \
                else b.configure(bg=C["sec_bg"], fg=C["sec_fg"])

    def _browse(self):
        p = filedialog.askdirectory(title="Select Folder")
        if p: self.folder_var.set(os.path.normpath(p))

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg+"\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.root.update_idletasks()

    def _start(self):
        if self.running: return
        if not PIL_AVAILABLE:
            messagebox.showerror("Missing Dependencies", "Run: pip install Pillow piexif")
            return
        folder = self.folder_var.get()
        if not folder:
            messagebox.showwarning("Select a Folder", "Browse to a folder containing images or videos first.")
            return
        self.running = True
        self.start_btn.configure(state="disabled", text="Processing…")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0","end")
        self.log_box.configure(state="disabled")
        threading.Thread(target=self._worker, args=(folder,), daemon=True).start()

    def _worker(self, folder):
        key = self.device_var.get()
        sid = self.synthid_var.get()
        randomize_location = self.location_var.get()
        self._log(f"Device: {PROFILES[key]['label']}  ·  SynthID removal: {'on' if sid else 'off'}  ·  GPS randomization: {'on' if randomize_location else 'off'}\n")

        out_dir = os.path.join(folder, "metadata_output")
        os.makedirs(out_dir, exist_ok=True)

        files = [f for f in os.listdir(folder) if not os.path.isdir(os.path.join(folder,f))]
        imgs  = [f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTS]
        vids  = [f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXTS]
        self._log(f"{len(imgs)} image(s)  ·  {len(vids)} video(s)\n")

        ok=fail=0
        for f in imgs:
            try:   process_image(os.path.join(folder,f), out_dir, key, sid, self._log, randomize_location); ok+=1
            except Exception as e: self._log(f"  ✗  {f} → {e}"); fail+=1
        for f in vids:
            try:   process_video(os.path.join(folder,f), out_dir, key, sid, self._log, randomize_location); ok+=1
            except Exception as e: self._log(f"  ✗  {f} → {e}"); fail+=1

        self._log(f"\n{'─'*50}\nDone  ·  {ok} processed  ·  {fail} failed\nOutput → {out_dir}")
        self.running = False
        self.start_btn.configure(state="normal", text="Start Simulation  →")


if __name__ == "__main__":
    if not TK_AVAILABLE:
        raise SystemExit("Tkinter is required for the desktop app. Run web_server.py for the web service.")
    root = tk.Tk()
    App(root)
    root.mainloop()
