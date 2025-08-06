import jinja2

from app.core.feature_interface import BaseFeature

class EasyOptions:
    def __init__(self, feature: BaseFeature):
        self.feature = feature
        self.options = {}


    def add_option(self, option_id: str, option_label: str, option_callable: callable) -> None:
        self.options[option_id] = {
            "label": option_label,
            "callable": option_callable
        }


    def render(self) -> str:
        template = jinja2.Template("""
            {% for opt in options %}
            <button onclick="runFeature('{{ feature }}', '{{ opt.id }}')">
                {{ opt.label }}
            </button>
            {% endfor %}
        """)

        html = template.render(options=self.options )