"""Spoof-correctness tests. Run: python -m pytest test_metadata.py -q

These assert the properties swarm relies on: metadata is rewritten to match the
target device, GPS lands in the US, source AI/provenance markers are gone, and
repeated processing of the same source never produces identical metadata.
"""
import os
import tempfile

import piexif
from PIL import Image

import metadata_simulator as m


def _make_source(path, make=b"Google", model=b"Pixel 8 Pro", software=b"Grok Imagine"):
    exif = {
        "0th": {
            piexif.ImageIFD.Make: make,
            piexif.ImageIFD.Model: model,
            piexif.ImageIFD.Software: software,
            piexif.ImageIFD.DateTime: b"2022:01:01 00:00:00",
        },
        "Exif": {},
        "GPS": {  # Tokyo — a non-US point that must be overwritten
            piexif.GPSIFD.GPSLatitudeRef: b"N",
            piexif.GPSIFD.GPSLatitude: ((35, 1), (40, 1), (3432, 100)),
            piexif.GPSIFD.GPSLongitudeRef: b"E",
            piexif.GPSIFD.GPSLongitude: ((139, 1), (39, 1), (1080, 100)),
        },
        "1st": {},
        "thumbnail": None,
    }
    Image.new("RGB", (600, 800), (40, 80, 120)).save(path, "JPEG", exif=piexif.dump(exif))


def test_device_model_resolution():
    assert m.resolve_profile("iphone15,4") == "IPHONE_15"
    assert m.resolve_profile("iphone16,1") == "IPHONE_15_PRO"
    assert m.resolve_profile("iPhone 15 Pro") == "IPHONE_15_PRO"
    assert m.resolve_profile("iphone14,7") == "IPHONE_14"
    assert m.resolve_profile("some-android-thing") == "PIXEL_8"
    assert m.resolve_profile(None) == m.DEFAULT_PROFILE


def test_image_spoof_matches_device_and_is_us():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in.jpg")
        _make_source(src)
        out = m.process_image(src, d, "IPHONE_15", True, lambda *_: None, True)
        assert m.verify_image_spoof(out, "IPHONE_15")["verified"] is True
        meta = m.read_image_metadata(out)
        assert meta["Make"] == "Apple"
        assert meta["Model"] == "iPhone 15"


def test_source_ai_markers_are_stripped():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in.jpg")
        _make_source(src, software=b"Grok Imagine")
        out = m.process_image(src, d, "IPHONE_15", True, lambda *_: None, True)
        meta = m.read_image_metadata(out)
        assert "Grok" not in str(meta["Software"])
        assert meta["Make"] != "Google"


def test_repeat_processing_is_never_identical():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in.jpg")
        _make_source(src)
        names, stamps, points = set(), set(), set()
        for _ in range(8):
            out = m.process_image(src, d, "IPHONE_15", True, lambda *_: None, True)
            meta = m.read_image_metadata(out)
            names.add(os.path.basename(out))
            stamps.add(meta["DateTimeOriginal"])
            gps = meta["GPSLatitude"]
            points.add((gps[0][0], gps[1][0], gps[2][0]))
        assert len(names) == 8, "filenames must be unique per post"
        assert len(stamps) >= 7, "timestamps must vary per post"
        assert len(points) >= 7, "GPS points must vary per post"
