import webview
import sys
import os
import jinja2
import importlib.util

import app_constants
import web_templates
from app import feature_interface


class API:
    def __init__(self, loaded_features):
        self.loaded_features = loaded_features
        self.file_path = None

    def set_file_path(self, file_path):
        self.file_path = file_path

    def render_side_bar(self):
        template =jinja2.Template(web_templates.LEFT_BAR_FEATURE_TEMPLATE)
        render = template.render(features=app_constants.APP_FEATURES)
        return render

    def invoke_feature(self, feature_name: str):
        feature = self.loaded_features[feature_name]
        response = feature.run(self.file_path)

        return response

if __name__ == '__main__':
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PARENT_DIR = os.path.dirname(BASE_DIR)

    WEB_DIR = os.path.join(PARENT_DIR, "web")
    INDEX_HTML = os.path.join(WEB_DIR, app_constants.MAIN_WINDOW_HTML_NAME)
    FEATURE_DIR = os.path.join(BASE_DIR, "features")

    # feature scan
    loaded_features = {}
    for feature in app_constants.APP_FEATURES:
        feature_name = feature['name']
        feature_version = feature['version']

        feature_file = os.path.join(FEATURE_DIR, feature_name, feature_version, f"{feature_name}.py")

        if not os.path.exists(feature_file):
            raise Exception(f"Feature file not found: {feature_file}")

        # Load the module dynamically
        spec = importlib.util.spec_from_file_location(feature_name, feature_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # call register()
        if not hasattr(module, "register"):
            raise Exception(f"Feature file does not have a register() function: {feature_file}")

        instance = module.register()

        if not isinstance(instance, feature_interface.BaseFeature):
            raise Exception(f"Feature register() function did not return a BaseFeature instance: {feature_file}")

        loaded_features[feature_name] = instance


    try:
        app_api = API(loaded_features)
        window = webview.create_window(app_constants.APP_NAME + " " + app_constants.APP_VERSION, INDEX_HTML, js_api=app_api)
        webview.start(debug=True)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)