from jinja2 import Template
from app.core.contracts.feature_interface import BaseFeature
from app.core.easy_options import EasyOptions

import subprocess
import os

def register():
    instance = Feature()

    easy_options = EasyOptions("Zsteg Options:")
    easy_options.add_option("hello", "Say Hello", instance.hello)
    easy_options.add_option("run", "Run zsteg on a file", instance.run_default)

    return {
        "instance": instance,
        "self_test": lambda: True,
        "shutdown": lambda: print("Shutting down zsteg..."),
        "easy_options": easy_options,
    }

class Feature(BaseFeature):

    def shutdown(self):
            print("Shutting down zsteg...")

    def hello(self, params: dict = None) -> str:
        return f"Hello from zsteg with params: {params}!"

    def run_default(self, params: dict) -> str:

        file_path = params.get("file_path")
        # Check if the file path is valid
        if not file_path or not os.path.isfile(file_path):
            return "<p>No file selected or invalid path.</p>"
        
        try:
            
            # Get the absolute path to the shell script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, 'runzsteg.sh')
            
            # Check if the script exists
            if not os.path.exists(script_path):
                return f"Error: Script '{script_path}' not found"
            
            # Make sure the script is executable
            os.chmod(script_path, 0o755)

            # Set environment variable to force non-interactive mode
            env = os.environ.copy()
            env['NON_INTERACTIVE'] = 'true'
            
            # Run the shell script with the image path
            result = subprocess.run([script_path, file_path],
                                    capture_output=True,
                                    text=False,  # Get bytes instead
                                    timeout=60,
                                    env=env,
                                    stdin=subprocess.DEVNULL
                                    )
            
            # Decode with error handling
            try:
                stdout_text = result.stdout.decode('utf-8')
                stderr_text = result.stderr.decode('utf-8') if result.stderr else ""
            except UnicodeDecodeError:
                # Fallback to latin-1 or ignore errors
                stdout_text = result.stdout.decode('utf-8', errors='replace')
                stderr_text = result.stderr.decode('utf-8', errors='replace') if result.stderr else ""

            print(f"[DEBUG] Return code: {result.returncode}")
            print(f"[DEBUG] STDOUT length: {len(result.stdout)}")
            print(f"[DEBUG] STDERR length: {len(result.stderr)}")
            print(f"[DEBUG] First 200 chars of stdout: {result.stdout[:200]}")
            
            if result.returncode != 0:
                return f"Error: {result.stderr.strip() if result.stderr else 'Unknown error occurred'}"
            
            # Render HTML using Jinja2
            template_str = """
            <style>
                .zsteg-container {
                    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                    max-width: 100%;
                    margin: 20px 0;
                }
                .zsteg-output {
                    background-color: #f8f9fa;
                    border: 1px solid #e9ecef;
                    border-radius: 8px;
                    padding: 20px;
                    overflow-x: auto;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    font-size: 14px;
                    line-height: 1.4;
                    color: #333;
                }
                .file-info {
                    background-color: #e7f3ff;
                    border-left: 4px solid #007bff;
                    padding: 10px 15px;
                    margin: 10px 0;
                    border-radius: 4px;
                }
                .zsteg-title {
                    color: #2c3e50;
                    border-bottom: 2px solid #3498db;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }
            </style>
            <div class="zsteg-container">
                <h2 class="zsteg-title">🔍 Zsteg Analysis Results</h2>
                <div class="file-info">
                    <strong>📁 File:</strong> <code>{{ filename }}</code>
                </div>
                <div class="zsteg-output">{{ output | e }}</div>
            </div>
            """

            template = Template(template_str)
            return template.render(filename=os.path.basename(file_path), output=stdout_text)

        except subprocess.TimeoutExpired:
            return "Error: zsteg analysis timed out"
        except subprocess.CalledProcessError as e:
            return f"Error running zsteg: {e.stderr.strip() if e.stderr else str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
