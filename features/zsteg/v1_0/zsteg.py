from app.core.contracts.feature_interface import BaseFeature

import subprocess
import os

def register():
    instance = Feature()
    return {
        "instance": instance,
        "self_test": lambda: True,
        "shutdown": lambda: print("Shutting down zsteg..."),
    }

class Feature(BaseFeature):

    def run(self, file_path) -> str:

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
            
            # Run the shell script with the image path
            result = subprocess.run([script_path, file_path],
                                    capture_output=True,
                                    text=True,
                                    timeout=60  # Add timeout to prevent hanging
                                    )
            print(result)
            
            if result.returncode != 0:
                return f"Error: {result.stderr.strip() if result.stderr else 'Unknown error occurred'}"
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            return "Error: zsteg analysis timed out"
        except subprocess.CalledProcessError as e:
            return f"Error running zsteg: {e.stderr.strip() if e.stderr else str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
