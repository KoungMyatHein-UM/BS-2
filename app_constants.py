APP_NAME = "MaasSec BigSister"
APP_VERSION = "0.1"

HTML_NAME = "index.html"
DEFAULT_WINDOW_DIMENSIONS = (1280, 800)
MIN_WINDOW_DIMENSIONS = (800, 500)

SUPPORTED_FILE_TYPES = [("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")]

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

    "Feature_2": {
        "version": "v1_0",
        "display_name": "Feature 2",
        "description": "This is the second feature",
        "icon": "icon_2.png"
    },

    "Feature_3": {
        "version": "v1_0",
        "display_name": "Feature 3",
        "description": "This is the third feature",
        "icon": "icon_3.png"
    },

    "Feature_4": {
        "version": "v1_0",
        "display_name": "Feature 4",
        "description": "This is the fourth feature",
        "icon": "icon_3.png"
    },

    "Feature_5": {
        "enabled": False,
        "version": "v1_0",
        "display_name": "Feature 4",
        "description": "This is the fourth feature",
        "icon": "icon_3.png"
    }
}