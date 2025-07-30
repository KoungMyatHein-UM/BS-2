import jinja2

from app.ui import web_templates
from app.core.feature_manager import FeatureManager


class API:
    def __init__(self, feature_manager: FeatureManager):
        self.feature_manager = feature_manager
        self.file_path = None

    def set_file_path(self, file_path):
        self.file_path = file_path

    def render_side_bar(self):
        template =jinja2.Template(web_templates.LEFT_BAR_FEATURE_TEMPLATE)
        render = template.render(features=self.feature_manager.get_available_features())
        return render

    def invoke_feature(self, feature_name: str):
        feature = self.feature_manager.get_feature(feature_name)
        response = feature.run(self.file_path)

        return response