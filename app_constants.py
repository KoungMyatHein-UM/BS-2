APP_NAME = "MaasSec BigSister"
APP_VERSION = "0.1"

HTML_NAME = "index.html"
DEFAULT_WINDOW_DIMENSIONS = (1280, 800)
MIN_WINDOW_DIMENSIONS = (800, 500)

SUPPORTED_FILE_TYPES = [("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")]

# TODO: implement description as tooltip on hover
# TODO: implement caching logic
DEFAULTS = {
    "enabled": True,
    "cached": True,
    "version": "v1_0",
    "display_name": None,
    "description": None,
    "icon": None,
}

APP_FEATURES = {
    "exiftool_scraper": {
        "version": "v1_0",
        "display_name": "EXIFTool Scraper",
        "description": "This feature allows you to scrape EXIF data from images",
        "icon": "icon_exiftool.png"
    },

    "zsteg": {
        "version": "v1_0",
        "display_name": "Zsteg Analysis",
        "description": "This is the second feature",
        "icon": "icon_zsteg.png"
    },

    "steghide": {
        "version": "v1_0",
        "display_name": "Steghide Analysis",
        "description": "This is the third feature",
        "icon": "icon_3.png"
    },

    "binwalk": {
        "version": "v1_0",
        "display_name": "Binwalk Analysis",
        "description": "This is the fourth feature",
        "icon": "icon_3.png"
    },

    "Feature_5": {
        "enabled": False,
        "version": "v1_0",
        "display_name": "Feature 5",
        "description": "This is the fifth feature",
        "icon": "icon_3.png"
    }
}