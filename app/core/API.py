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

    def select_file(self):
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)

        filepath = filedialog.askopenfilename(
            filetypes=self.supported_files
        )
        root.destroy()

        self.file_path = filepath
        # reinvoke
        webview.windows[0].evaluate_js(f'invokeFeature("{self.current_feature}")')

        return filepath

    def render_side_bar(self):
        template =jinja2.Template(web_templates.LEFT_BAR_FEATURE_TEMPLATE)
        render = template.render(features=self.feature_manager.get_available_features())
        return render

    def invoke_feature(self, feature_name: str):
        self.current_feature = feature_name

        feature = self.feature_manager.get_feature(feature_name)
        response = feature.run(self.file_path)

        return response