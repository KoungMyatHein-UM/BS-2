import jinja2
from app.core.contracts.easy_options_interface import BaseEasyOptions

class EasyOptions(BaseEasyOptions):
    def __init__(self, message: str = ""):
        self.message = message
        self.feature_name = None
        self.options = {}


    def add_option(self, option_id: str, option_label: str, option_callable: callable) -> None:
        self.options[option_id] = {
            "id": option_id,
            "label": option_label,
            "callable": option_callable
        }


    def set_feature_name(self, feature_name: str) -> None:
        self.feature_name = feature_name


    def render(self) -> str:
        if not self.feature_name:
            raise ValueError("Feature name not set for EasyOptions rendering.")
        if not self.options:
            return "<p>No options available.</p>"

        template = jinja2.Template("""
            {% if message %}
            <h2>{{ message }}</h2>
            {% endif %}
            {% for opt in options %}
            <button onclick="runFeature('{{ feature_name }}', '{{ opt.id }}')">
                {{ opt.label }}
            </button>
            {% endfor %}
        """)

        return template.render(message=self.message, feature_name=self.feature_name, options=self.options.values())


    def get_option_callable(self, option_id: str) -> callable:
        return self.options[option_id]["callable"]