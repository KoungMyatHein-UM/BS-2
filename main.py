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
    index_html = os.path.join(web_dir, app_constants.MAIN_WINDOW_HTML_NAME)
    feature_dir = os.path.join(base_dir, "features")

    feature_manager = FeatureManager(feature_dir, app_constants.APP_FEATURES)
    app_api = API(feature_manager)
    window = webview.create_window(app_constants.APP_NAME + " " + app_constants.APP_VERSION, str(index_html), js_api=app_api)
    webview.start(debug=True)


if __name__ == '__main__':

    try:
        start_app()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)