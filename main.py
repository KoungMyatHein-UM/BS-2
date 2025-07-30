import webview
import sys
import os

import app_constants
from app.core.API import API
from app.core.feature_manager import FeatureManager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def start_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    web_dir = os.path.join(base_dir, "web")
    index_html = os.path.join(web_dir, app_constants.HTML_NAME)

    feature_manager = FeatureManager(app_constants.APP_FEATURES)
    app_api = API(feature_manager)
    window = webview.create_window(
        f"{app_constants.APP_NAME} {app_constants.APP_VERSION}",
        str(index_html),
        js_api=app_api,

        width=app_constants.DEFAULT_WINDOW_DIMENSIONS[0],
        height=app_constants.DEFAULT_WINDOW_DIMENSIONS[1],
        resizable=True,
        fullscreen=False,
        min_size=app_constants.MIN_WINDOW_DIMENSIONS,
        confirm_close=True
    )
    webview.start(debug=True)


if __name__ == '__main__':

    try:
        start_app()
    except IndexError as e:
        print(f"Error: {e}", file=sys.stderr)