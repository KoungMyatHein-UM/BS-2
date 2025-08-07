from jinja2 import Template
from app.core.contracts.feature_interface import BaseFeature
from app.core.easy_options import EasyOptions

import subprocess
import os

def register():
    instance = Feature()

    easy_options = EasyOptions("Binwalk Options:")
    easy_options.add_option("hello","Hello", instance.hello)
    easy_options.add_option("run", "Run Binwalk", instance.run_default)

    return {
        "instance": instance,
        "self_test": None,
        "shutdown": lambda: print("Shutting down Feature_2..."),
        "easy_options": easy_options
    }

class Feature(BaseFeature):

    def hello(self, params: dict = None) -> str:
        return f"Hello from binwalk with params: {params}!"

    def run_default(self, params: dict) -> str:
        file_path = params.get("file_path")

        if not file_path or not os.path.isfile(file_path):
            return "<p>No file selected or invalid path.</p>"

        print("Running Feature_2")
        print("Hello from Feature_2.0.0! This is a feature that is part of the app's default installation.")

        template_str = """
        <h2>Feature_2</h2>
        <p>Provided path: {{ file_path }}</p>
        """
        template = Template(template_str)
        return template.render(file_path=file_path)