import re
from jinja2 import Template
from app.core.contracts.feature_interface import BaseFeature
from app.core.easy_options import EasyOptions

import subprocess
import os

def register():
    instance = Feature()

    easy_options = EasyOptions("Binwalk Options:")
    easy_options.add_option("run", "Run Signature Scan", instance.scan_signatures)
    easy_options.add_option("extract", "Extract Embedded Files", instance.extract_files)
    easy_options.add_option("entropy", "Perform Entropy Analysis", instance.entropy_analysis)


    return {
        "instance": instance,
        "self_test": None,
        "shutdown": lambda: print("Shutting down Feature_2..."),
        "easy_options": easy_options
    }

class Feature(BaseFeature):

    def shutdown(self):
        print("Shutting down Binwalk...")

    def run_default(self, params):
        return self.scan_signatures(params)

    def scan_signatures(self, params: dict) -> str:
        file_path = params.get("file_path")

        if not file_path or not os.path.isfile(file_path):
            return "<p>No file selected or invalid path.</p>"

        try:
            result = subprocess.run(
                ["binwalk", file_path],
                capture_output=True,
                text=True,
                timeout=60,
                stdin=subprocess.DEVNULL
            )

            if result.returncode != 0:
                return f"<p>Error running binwalk: {result.stderr}</p>"
            signatures = self._parse_signatures(result.stdout)


            template_str = """
            <h2>🔍 Binwalk Signature Scan</h2>
            <p><strong>File:</strong> {{ filename }}</p>
            
            {% if signatures %}
            <table style="border-collapse: collapse; width: 100%; margin: 15px 0;">
                <thead>
                    <tr style="background-color: #f2f2f2;">
                        <th style="border: 1px solid #ddd; padding: 8px;">Offset</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Hex Offset</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Description</th>
                    </tr>
                </thead>
                <tbody>
                {% for sig in signatures %}
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px;">{{ sig.offset }}</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{{ sig.hex_offset }}</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{{ sig.description }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p>No embedded signatures detected.</p>
            {% endif %}
            
            <h3>Raw Output</h3>
            <pre style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto;">{{ raw_output }}</pre>
            """

            template = Template(template_str)
            return template.render(
                filename=os.path.basename(file_path),
                signatures=signatures,
                raw_output=result.stdout
            )
    
        except subprocess.TimeoutExpired:
            return "<p>Error: Binwalk command timed out.</p>"
        except Exception as e:
            return f"<p>Error running binwalk: {e}</p>"
        
    def extract_files(self, params: dict) -> str:
        """Extract embedded files from the given file using binwalk"""
        file_path = params.get("file_path")

        if not file_path or not os.path.isfile(file_path):
            return "<p>No file selected or invalid path.</p>"

        try:
            result = subprocess.run(
                ["binwalk", "-e", file_path],
                capture_output=True,
                text=True,
                timeout=60,
                stdin=subprocess.DEVNULL
            )

            if result.returncode != 0:
                return f"<p>Error running binwalk: {result.stderr}</p>"

            template_str = """
            <h2>📦 Binwalk File Extraction</h2>
            <p><strong>File:</strong> {{ filename }}</p>
            <pre style="background-color: #f5f5f5; padding: 15px; border-radius: 5px;">{{ output }}</pre>
            """

            template = Template(template_str)
            return template.render(
                filename=os.path.basename(file_path),
                output=result.stdout
            )
        
        except subprocess.TimeoutExpired:
            return "<p>Error: Binwalk command timed out.</p>"
        except Exception as e:
            return f"<p>Error running binwalk: {e}</p>"
    
    def entropy_analysis(self, params: dict) -> str:
        """Perform entropy analysis"""
        file_path = params.get("file_path")
        if not file_path or not os.path.isfile(file_path):
            return "<p>No file selected or invalid path.</p>"

        try:
            result = subprocess.run(
                ["binwalk", "-E", file_path],
                capture_output=True,
                text=True,
                timeout=60,
                stdin=subprocess.DEVNULL
            )
            
            if result.returncode != 0:
                return f"<p>Error running entropy analysis: {result.stderr}</p>"

            template_str = """
            <h2>📊 Binwalk Entropy Analysis</h2>
            <p><strong>File:</strong> {{ filename }}</p>
            <pre style="background-color: #f5f5f5; padding: 15px; border-radius: 5px;">{{ output }}</pre>
            """

            template = Template(template_str)
            return template.render(
                filename=os.path.basename(file_path),
                output=result.stdout
            )

        except subprocess.TimeoutExpired:
            return "<p>Error: Entropy analysis timed out.</p>"
        except Exception as e:
            return f"<p>Error running entropy analysis: {str(e)}</p>"
    
    def _parse_signatures(self, output: str) -> list:
        """Parse binwalk output to extract signature information"""
        signatures = []
        
        # Pattern to match binwalk signature lines: offset, hex offset, description
        pattern = re.compile(r'^\s*(\d+)\s+(0x[0-9A-Fa-f]+)\s+(.+)$')
        
        for line in output.splitlines():
            match = pattern.match(line)
            if match:
                signatures.append({
                    'offset': match.group(1),
                    'hex_offset': match.group(2),
                    'description': match.group(3).strip()
                })
        
        return signatures

