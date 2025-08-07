from jinja2 import Template
from app.core.contracts.feature_interface import BaseFeature
from app.core.easy_options import EasyOptions

import subprocess
import os

def register():
    instance = Feature()

    easy_options = EasyOptions("Steghide Options:")
    easy_options.add_option("hello", "Say Hello", instance.hello)
    easy_options.add_option("run", "Run Steghide on a file", instance.run_default)

    return {
        "instance": instance,
        "self_test": lambda: True,
        "shutdown": lambda: print("Shutting down Steghide..."),
        "easy_options": easy_options,
    }

class Feature(BaseFeature):

    def shutdown(self):
        print("Shutting down Steghide...")

    def hello(self, params: dict = None) -> str:
        return f"Hello from Steghide with params: {params}!"

    def run_default(self, params: dict) -> str:
        file_path = params.get("file_path")
        # Check if the file path is valid
        if not file_path or not os.path.isfile(file_path):
            return "<p>No file selected or invalid path.</p>"
        
        try:
            # Get the absolute path to the shell script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, 'runsteghide.sh')
            
            # Check if the script exists
            if not os.path.exists(script_path):
                return f"Error: Script '{script_path}' not found"
            
            # Make sure the script is executable
            os.chmod(script_path, 0o755)

            # Run the shell script with the image path
            result = subprocess.run([script_path, file_path],
                                    capture_output=True,
                                    text=True,  # Get text output
                                    timeout=60,
                                    stdin=subprocess.DEVNULL)
            
            if result.returncode != 0:
                return f"Error running Steghide: {result.stderr}"
            
            template_str = """
            <p>Steghide output:</p>
            <pre>{{ output }}</pre>"""
            
            return f"<p>Steghide output:<br>{result.stdout}</p>"
        except subprocess.TimeoutExpired:
            return "<p>Error: Steghide command timed out.</p>"
        except Exception as e:
            return f"<p>Error running Steghide: {str(e)}</p>"