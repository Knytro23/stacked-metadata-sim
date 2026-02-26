"""
Stacked Metadata Simulator v2.3
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
PROFILES = {
    "IPHONE_15":   {"label": "iPhone 15 Pro",    "Make": "Apple",   "Model": "iPhone 15 Pro",     "Software": "17.2.1",        "LensMake": "Apple",   "LensModel": "iPhone 15 Pro back triple camera 6.765mm f/1.78", "FocalLength": (677,100), "FNumber": (178,100), "ExposureTime": (1,1000), "ISO": 50,  "Flash": 24, "WB": 0, "CS": 1, "EV": b"0232", "FPV": b"0100", "ffmeta": {"make":"Apple","model":"iPhone 15 Pro","com.apple.quicktime.make":"Apple","com.apple.quicktime.model":"iPhone 15 Pro","com.apple.quicktime.software":"17.2.1"}},
    "SAMSUNG_S24": {"label": "Samsung S24 Ultra", "Make": "samsung", "Model": "SM-S928B",          "Software": "S928BXXU2AXCA", "LensMake": "Samsung", "LensModel": "Samsung Galaxy S24 Ultra rear camera 6.3mm f/1.7",  "FocalLength": (630,100), "FNumber": (170,100), "ExposureTime": (1,1200), "ISO": 64,  "Flash": 0,  "WB": 0, "CS": 1, "EV": b"0220", "FPV": b"0100", "ffmeta": {"make":"samsung","model":"SM-S928B"}},
    "PIXEL_8":     {"label": "Pixel 8 Pro",       "Make": "Google",  "Model": "Pixel 8 Pro",       "Software": "HDR+ 1.0.560z", "LensMake": "Google",  "LensModel": "Pixel 8 Pro back camera 6.81mm f/1.68",          "FocalLength": (681,100), "FNumber": (168,100), "ExposureTime": (1,800),  "ISO": 80,  "Flash": 0,  "WB": 0, "CS": 1, "EV": b"0231", "FPV": b"0100", "ffmeta": {"make":"Google","model":"Pixel 8 Pro"}},
}

LOCATIONS = [
    {"name":"New York City", "lat": 40.7128, "lon": -74.0060},
    {"name":"Los Angeles",   "lat": 34.0522, "lon":-118.2437},
    {"name":"Miami",         "lat": 25.7617, "lon": -80.1918},
    {"name":"London",        "lat": 51.5074, "lon":  -0.1278},
    {"name":"Paris",         "lat": 48.8566, "lon":   2.3522},
    {"name":"Tokyo",         "lat": 35.6762, "lon": 139.6503},
    {"name":"Dubai",         "lat": 25.2048, "lon":  55.2708},
    {"name":"Sydney",        "lat":-33.8688, "lon": 151.2093},
]

IMAGE_EXTS = {".jpg",".jpeg",".tiff",".tif",".png",".webp",".heic"}
VIDEO_EXTS = {".mp4",".mov",".avi",".mkv",".m4v",".3gp"}


def _res(name):
    """Path to bundled resource (works frozen + dev)."""
    base = os.path.dirname(sys.executable) if getattr(sys,'frozen',False) \
           else os.path.dirname(os.path.abspath(__file__))
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

def _rand_loc(): return random.choice(LOCATIONS)
def _rand_ts():  return (datetime.datetime.now()-datetime.timedelta(days=random.randint(1,730))).strftime("%Y:%m:%d %H:%M:%S")
def _rand_tsiso(): return (datetime.datetime.now()-datetime.timedelta(days=random.randint(1,730))).strftime("%Y-%m-%dT%H:%M:%S")
def _rand_fn(ext): return "IMG_"+"".join(random.choices(string.digits,k=8))+ext

def _synthid_strip(img):
    w,h=img.size
    img=img.resize((int(w*.997),int(h*.997)),Image.LANCZOS).resize((w,h),Image.LANCZOS)
    return img.filter(ImageFilter.SMOOTH_MORE).filter(ImageFilter.SHARPEN)

def process_image(src, out_dir, key, sid, log):
    p=PROFILES[key]; ts=_rand_ts(); loc=_rand_loc(); lat,lon=loc["lat"],loc["lon"]
    exif={"0th":{piexif.ImageIFD.Make:p["Make"].encode(),piexif.ImageIFD.Model:p["Model"].encode(),piexif.ImageIFD.Software:p["Software"].encode(),piexif.ImageIFD.DateTime:ts.encode()},
          "Exif":{piexif.ExifIFD.DateTimeOriginal:ts.encode(),piexif.ExifIFD.LensMake:p["LensMake"].encode(),piexif.ExifIFD.LensModel:p["LensModel"].encode(),piexif.ExifIFD.FocalLength:p["FocalLength"],piexif.ExifIFD.FNumber:p["FNumber"],piexif.ExifIFD.ExposureTime:p["ExposureTime"],piexif.ExifIFD.ISOSpeedRatings:p["ISO"],piexif.ExifIFD.Flash:p["Flash"],piexif.ExifIFD.WhiteBalance:p["WB"],piexif.ExifIFD.ColorSpace:p["CS"],piexif.ExifIFD.ExifVersion:p["EV"],piexif.ExifIFD.FlashpixVersion:p["FPV"]},
          "GPS":{piexif.GPSIFD.GPSLatitudeRef:b"N" if lat>=0 else b"S",piexif.GPSIFD.GPSLatitude:_dms(lat),piexif.GPSIFD.GPSLongitudeRef:b"E" if lon>=0 else b"W",piexif.GPSIFD.GPSLongitude:_dms(lon)},
          "1st":{},"thumbnail":None}
    img=Image.open(src).convert("RGB")
    if sid: img=_synthid_strip(img)
    out=os.path.join(out_dir,_rand_fn(".jpg"))
    img.save(out,"JPEG",exif=piexif.dump(exif),quality=95)
    log(f"  ✓  {os.path.basename(src)} → {os.path.basename(out)}  [{p['label']} · {loc['name']}{'  · SynthID✗' if sid else ''}]")

def process_video(src, out_dir, key, sid, log):
    p=PROFILES[key]; ts=_rand_tsiso(); loc=_rand_loc(); lat,lon=loc["lat"],loc["lon"]
    out=os.path.join(out_dir,_rand_fn(".mp4"))
    cmd=["ffmpeg","-y","-i",src]
    if sid: cmd+=["-vf","scale=iw*0.997:ih*0.997,scale=iw/0.997:ih/0.997,unsharp=3:3:0.3","-c:v","libx264","-crf",str(random.randint(19,22)),"-preset","slow","-c:a","aac","-b:a","192k"]
    else:   cmd+=["-c:v","libx264","-crf","20","-preset","medium","-c:a","aac"]
    for k,v in p["ffmeta"].items(): cmd+=["-metadata",f"{k}={v}"]
    cmd+=["-metadata",f"creation_time={ts}","-metadata",f"location={lat:+.4f}{lon:+.4f}/","-movflags","+faststart",out]
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode!=0: raise RuntimeError(r.stderr[-200:])
    log(f"  ✓  {os.path.basename(src)} → {os.path.basename(out)}  [{p['label']} · {loc['name']}{'  · SynthID✗' if sid else ''}]")


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

        tk.Label(foot, text="© Stacked · stacked.com",
                 font=F["sub"], fg=C["sub"], bg=C["bg"]).pack(side="right")

        # ── NAVBAR ────────────────────────────────────────────────────────────
        nav = tk.Frame(self.root, bg=C["bg"], height=54)
        nav.pack(side="top", fill="x")
        nav.pack_propagate(False)

        logo_path = _res("stacked_logo.png")
        if os.path.exists(logo_path) and PIL_AVAILABLE:
            try:
                raw = Image.open(logo_path).convert("RGBA")
                lh = 26
                raw = raw.resize((int(raw.width/raw.height*lh), lh), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(raw)
                tk.Label(nav, image=self._logo_img, bg=C["bg"]).pack(side="left", padx=28, pady=14)
            except Exception:
                tk.Label(nav, text="✦ Stacked", font=F["hero"], fg=C["text"], bg=C["bg"]).pack(side="left", padx=28, pady=12)
        else:
            tk.Label(nav, text="✦ Stacked", font=F["hero"], fg=C["text"], bg=C["bg"]).pack(side="left", padx=28, pady=12)

        tk.Label(nav, text="Metadata Simulator", font=F["nav"], fg=C["sub"], bg=C["bg"]).pack(side="left")

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
        self._log(f"Device: {PROFILES[key]['label']}  ·  SynthID removal: {'on' if sid else 'off'}\n")

        out_dir = os.path.join(folder, "stacked_output")
        os.makedirs(out_dir, exist_ok=True)

        files = [f for f in os.listdir(folder) if not os.path.isdir(os.path.join(folder,f))]
        imgs  = [f for f in files if os.path.splitext(f)[1].lower() in IMAGE_EXTS]
        vids  = [f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXTS]
        self._log(f"{len(imgs)} image(s)  ·  {len(vids)} video(s)\n")

        ok=fail=0
        for f in imgs:
            try:   process_image(os.path.join(folder,f), out_dir, key, sid, self._log); ok+=1
            except Exception as e: self._log(f"  ✗  {f} → {e}"); fail+=1
        for f in vids:
            try:   process_video(os.path.join(folder,f), out_dir, key, sid, self._log); ok+=1
            except Exception as e: self._log(f"  ✗  {f} → {e}"); fail+=1

        self._log(f"\n{'─'*50}\nDone  ·  {ok} processed  ·  {fail} failed\nOutput → {out_dir}")
        self.running = False
        self.start_btn.configure(state="normal", text="Start Simulation  →")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
