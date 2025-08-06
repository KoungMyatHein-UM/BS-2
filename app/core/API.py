import jinja2
import tkinter as tk
from tkinter import filedialog
import webview

from app.ui import web_templates
from app.core.feature_manager import FeatureManager


class API:
    def __init__(self, feature_manager: FeatureManager, supported_files: list, feature_reload_on_file_change: bool = True):
        self.feature_reload = feature_reload_on_file_change

        self.feature_manager = feature_manager
        self.file_path = None
        self.last_used_feature = None
        self.supported_files = supported_files

        self._shutdown_handled = False

    # TODO: See below.
    # API EXPOSURE VULNERABILITY: this method is to be called by main.py on shutdown but is mixed in with front-end exposed methods
    # a rogue plugin can call this api to trigger an unintentional shutdown.
    # It's fine for now since this tool is for in-house development only but we need to change it when we go public
    def shutdown(self):
        print("API Shutdown!")
        self.feature_manager.shutdown()

    # TODO: See below.
    # BAD CODE: API wrapper is doing too much business logic.
    # It's fine for now, but we should extract it to another file if it gets more complicated
    # or more methods get added
    def select_file(self):
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)

        filepath = filedialog.askopenfilename(
            filetypes=self.supported_files
        )
        root.destroy()

        if filepath is not None and filepath != "":
            self.file_path = filepath

            # reload the feature
            if self.feature_reload and self.last_used_feature is not None:
                webview.windows[0].evaluate_js(f'runFeature("{self.last_used_feature}")')

            return filepath
        else:
            return self.file_path

    # TODO: See below.
    # BAD CODE: API wrapper is doing too much business logic.
    # It's fine for now, but we should extract it to another file if it gets more complicated
    # or more methods get added
    def render_side_bar(self):
        template =jinja2.Template(web_templates.LEFT_BAR_FEATURE_TEMPLATE)
        render = template.render(features=self.feature_manager.get_available_features())
        return render

    def run_feature(self, feature_name: str):
        self.last_used_feature = feature_name

        response = self.feature_manager.invoke_feature(feature_name, self.file_path)

        return response