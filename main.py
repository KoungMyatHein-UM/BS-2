import webview
import sys
import os
import traceback

import app_constants
from app.core.API import API
from app.core.feature_manager import FeatureManager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app_api = None

def start_app(debug=False):
    global app_api

    base_dir = os.path.dirname(os.path.abspath(__file__))

    web_dir = os.path.join(base_dir, "web")
    index_html = os.path.join(web_dir, app_constants.HTML_NAME)

    feature_manager = FeatureManager(app_constants.DEFAULTS, app_constants.APP_FEATURES, debug=debug)
    app_api = API(feature_manager, app_constants.SUPPORTED_FILE_TYPES)
    main_window = webview.create_window(
        f"{app_constants.APP_NAME} {app_constants.APP_VERSION}",
        str(index_html),
        js_api=app_api,

        width=app_constants.DEFAULT_WINDOW_DIMENSIONS[0],
        height=app_constants.DEFAULT_WINDOW_DIMENSIONS[1],
        resizable=True,
        fullscreen=False,
        min_size=app_constants.MIN_WINDOW_DIMENSIONS,
        confirm_close=False
    )
    webview.start(gui='qt', debug=debug)

def handle_exit():
    if app_api:
        app_api.shutdown()
    sys.exit(0)


if __name__ == '__main__':
    try:
        start_app(debug=True)
    except Exception as e:
        traceback.print_exc()
    finally:
        handle_exit()