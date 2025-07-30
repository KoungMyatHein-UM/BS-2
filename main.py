import signal

import webview
import sys
import os

import app_constants
from app.core.API import API
from app.core.feature_manager import FeatureManager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app_api = None
main_window = None

_exit_handled = False

def start_app():
    global app_api
    global main_window

    base_dir = os.path.dirname(os.path.abspath(__file__))

    web_dir = os.path.join(base_dir, "web")
    index_html = os.path.join(web_dir, app_constants.HTML_NAME)

    feature_manager = FeatureManager(app_constants.APP_FEATURES)
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
    webview.start(gui='qt', debug=False)

def handle_exit(signum, frame):
    global _exit_handled
    if _exit_handled:
        return
    _exit_handled = True

    print("Caught exit signal. Shutting down...")

    if webview.windows:
        # Ask JS to call back into Python and shut us down cleanly
        webview.windows[0].evaluate_js("window.pywebview.api.shutdown()")

    if app_api:
        app_api.shutdown()

    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, handle_exit)

    try:
        start_app()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    finally:
        handle_exit(None, None)