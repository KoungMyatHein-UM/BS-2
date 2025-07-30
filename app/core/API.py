import jinja2
import tkinter as tk
from tkinter import filedialog
import webview

from app.ui import web_templates
from app.core.feature_manager import FeatureManager


class API:
    def __init__(self, feature_manager: FeatureManager, supported_files: list):
        self.feature_manager = feature_manager
        self.file_path = None
        self.current_feature = None
        self.supported_files = supported_files

        self._shutdown_handled = False

    def shutdown(self):
        if self._shutdown_handled:
            return
        else:
            self._shutdown_handled = True

            import sys
            print("Shutdown triggered from JS context")
            webview.windows[0].destroy()
            sys.exit(0)

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

            # reinvoke
            if self.current_feature is not None:
                webview.windows[0].evaluate_js(f'invokeFeature("{self.current_feature}")')

            return filepath
        else:
            return self.file_path


    def render_side_bar(self):
        template =jinja2.Template(web_templates.LEFT_BAR_FEATURE_TEMPLATE)
        render = template.render(features=self.feature_manager.get_available_features())
        return render

    def invoke_feature(self, feature_name: str):
        self.current_feature = feature_name

        feature = self.feature_manager.get_feature(feature_name)
        response = feature.run(self.file_path)

        return response