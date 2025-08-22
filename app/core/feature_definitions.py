from typing import Any, Dict

# Map: <feature_key> -> settings that override DEFAULTS.
# IMPORTANT: The keys must match your folder/file names:
#   features/<key>/<version>/<key>.py
FEATURE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "exiftool_scraper": {
        "enabled": True,
        "display_name": "ExifTool Scraper",
        "version": "v1_0",
        "description": "Extract EXIF and related metadata (exiftool/Pillow fallback).",
        "icon": "🧾",
    },
    "zsteg": {
        "enabled": True,
        "display_name": "Zsteg",
        "version": "v1_0",
        "description": "Detect/extract LSB-style stego in PNG/BMP via zsteg (Ruby).",
        "icon": "🧬",
    },
    "steghide": {
        "enabled": True,
        "display_name": "Steghide",
        "version": "v1_0",
        "description": "Inspect/extract stego payloads in JPG/BMP/WAV/AU via steghide.",
        "icon": "🔐",
    },
    "binwalk": {
        "enabled": True,
        "display_name": "Binwalk",
        "version": "v1_0",
        "description": "Scan/extract embedded firmware/files; entropy analysis.",
        "icon": "📦",
    },
    "iris": {
        "enabled": True,
        "display_name": "IRIS (Reverse Image Search)",
        "version": "v1_0",
        "description": "Automated reverse image search (Selenium/Chromium).",
        "icon": "🔎",
    },
}
