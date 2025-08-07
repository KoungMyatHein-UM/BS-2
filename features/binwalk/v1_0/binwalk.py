from jinja2 import Template

from app.core.contracts.feature_interface import BaseFeature

def register():
    instance = Feature()
    return {
        "instance": instance,
        "self_test": None,
        "shutdown": lambda: print("Shutting down Feature_2..."),
    }

class Feature(BaseFeature):
    def run(self, file_path) -> str:
        print("Running Feature_2")
        print("Hello from Feature_2.0.0! This is a feature that is part of the app's default installation.")

        template_str = """
        <h2>Feature_2</h2>
        <p>Provided path: {{ file_path }}</p>
        """
        template = Template(template_str)
        return template.render(file_path=file_path)