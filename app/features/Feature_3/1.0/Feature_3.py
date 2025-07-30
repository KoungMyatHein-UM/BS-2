from jinja2 import Template

from app.feature_interface import BaseFeature

class Feature(BaseFeature):
    def run(self, file_path=None) -> str:
        print("Running Feature_3")
        print("Hello from Feature_3.0.0! This is a feature that is part of the app's default installation.")

        template_str = """
        <h2>Feature_3</h2>
        <p>Provided path: {{ file_path }}</p>
        """
        template = Template(template_str)
        return template.render(file_path=file_path)

def register():
    return Feature()