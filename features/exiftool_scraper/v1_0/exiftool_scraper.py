import subprocess
import json
import os
from jinja2 import Template

from app.core.easy_options import EasyOptions
from app.core.contracts.feature_interface import BaseFeature

def register():
    instance = Feature()

    easy_options = EasyOptions("EXIFTools Scraper Options:")
    easy_options.add_option("file_path", "File Path", None)

    return {
        "instance": instance,
        "self_test": instance.self_test,
        "shutdown": instance.shutdown,
    }

class Feature(BaseFeature):
    def self_test(self):
        return True

    def shutdown(self):
        print("Shutting down exiftool_scraper...")

    def run_default(self, params: dict) -> str:
        file_path = params.get("file_path")
        if not file_path or not os.path.isfile(file_path):
            return "<p>No file selected or invalid path.</p>"

        try:
            # Run exiftool and get JSON output
            result = subprocess.run(
                ["exiftool", "-j", file_path],
                capture_output=True,
                text=True,
                check=True
            )
            metadata = json.loads(result.stdout)[0]
        except Exception as e:
            return f"<p>Error running exiftool: {e}</p>"

        # Render HTML using Jinja2
        template_str = """
        <h2>EXIFTool Metadata</h2>
        <p><strong>File:</strong> {{ file }}</p>
        <table>
            <thead><tr><th>Tag</th><th>Value</th></tr></thead>
            <tbody>
            {% for key, value in metadata.items() %}
                <tr><td>{{ key }}</td><td>{{ value }}</td></tr>
            {% endfor %}
            </tbody>
        </table>
        """

        template = Template(template_str)
        return template.render(file=os.path.basename(file_path), metadata=metadata)
