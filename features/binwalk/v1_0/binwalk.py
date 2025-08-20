from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from jinja2 import Template
from app.core.contracts.feature_interface import BaseFeature
from app.core.easy_options import EasyOptions

# =============================
# Normalized result structure
# =============================
@dataclass
class BinwalkResult:
    tool: str
    ok: bool
    action: str  # "scan" | "extract" | "entropy"
    file: str
    cmd: List[str]
    signatures: List[Dict[str, str]]  # for scan
    output_paths: List[str]           # for extract (dirs/files created)
    entropy: Optional[str]            # raw entropy text (if any)
    errors: Optional[str]
    raw: Dict[str, str]
    notes: List[str]

    def to_dict(self) -> Dict:
        return {
            "tool": self.tool,
            "ok": self.ok,
            "action": self.action,
            "file": self.file,
            "cmd": self.cmd,
            "signatures": self.signatures,
            "output_paths": self.output_paths,
            "entropy": self.entropy,
            "errors": self.errors,
            "raw": self.raw,
            "notes": self.notes,
        }


# =============================
# Platform helpers
# =============================
def _is_windows() -> bool:
    return platform.system() == "Windows"


def _detect_runtime() -> Tuple[str, Optional[List[str]], List[str]]:
    """
    Returns (mode, base_cmd, notes)
    mode: "native" | "wsl" | "unix" | "missing"
    base_cmd: ["binwalk"] or ["wsl", "-e", "binwalk"]
    """
    notes: List[str] = []
    if _is_windows():
        exe = shutil.which("binwalk")
        if exe:
            return "native", [exe], notes
        if shutil.which("wsl"):
            notes.append("Using WSL fallback for binwalk.")
            return "wsl", ["wsl", "-e", "binwalk"], notes
        notes.append("binwalk not found on PATH and WSL not available.")
        notes.append("Tip: install via WSL Ubuntu: `sudo apt update && sudo apt install -y binwalk`.")
        return "missing", None, notes
    else:
        exe = shutil.which("binwalk")
        if exe:
            return "unix", [exe], notes
        notes.append("binwalk not found on PATH.")
        notes.append("Tip (Debian/Ubuntu): `sudo apt install -y binwalk`.")
        return "missing", None, notes


def _to_wsl_path(win_path: str) -> str:
    drive, rest = os.path.splitdrive(win_path)
    drive_letter = drive.replace(":", "").lower()
    path = rest.replace("\\", "/")
    return f"/mnt/{drive_letter}{path}"


def _maybe_wsl_path(mode: str, p: str) -> str:
    if mode == "wsl" and _is_windows():
        return _to_wsl_path(os.path.abspath(p))
    return p


def _run(cmd: List[str], cwd: Optional[str] = None, timeout: int = 120, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=text,
        timeout=timeout,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        shell=False,
    )


# =============================
# Parsers / renderers
# =============================
_SIG_LINE = re.compile(r"^\s*(\d+)\s+(0x[0-9A-Fa-f]+)\s+(.+)$")

def _parse_signatures(output: str) -> List[Dict[str, str]]:
    signatures: List[Dict[str, str]] = []
    for line in output.splitlines():
        m = _SIG_LINE.match(line)
        if m:
            signatures.append({
                "offset": m.group(1),
                "hex_offset": m.group(2),
                "description": m.group(3).strip()
            })
    return signatures


_HTML_TEMPLATE = Template(
    """
<div class="panel">
  <h2>Binwalk – {{ result.action|capitalize }} ({{ "OK" if result.ok else "Failed" }})</h2>
  <p><b>File:</b> {{ result.file }}</p>
  <p><b>Command:</b> <code>{{ result.cmd|join(" ") }}</code></p>

  {% if result.notes %}
  <div class="notes">
    <ul>
    {% for n in result.notes %}
      <li>{{ n }}</li>
    {% endfor %}
    </ul>
  </div>
  {% endif %}

  {% if result.action == "scan" %}
    <h3>Signatures</h3>
    {% if result.signatures %}
      <table class="kv">
        <thead><tr><th>Offset</th><th>Hex</th><th>Description</th></tr></thead>
        <tbody>
        {% for s in result.signatures %}
          <tr><td>{{ s.offset }}</td><td>{{ s.hex_offset }}</td><td>{{ s.description }}</td></tr>
        {% endfor %}
        </tbody>
      </table>
    {% else %}
      <p><i>No signatures detected (or parser didn’t match). Check raw output.</i></p>
    {% endif %}
  {% endif %}

  {% if result.action == "extract" %}
    <h3>Output</h3>
    {% if result.output_paths %}
      <ul>
      {% for p in result.output_paths %}
        <li><code>{{ p }}</code></li>
      {% endfor %}
      </ul>
    {% else %}
      <p><i>No output paths found.</i></p>
    {% endif %}
  {% endif %}

  {% if result.action == "entropy" %}
    <h3>Entropy</h3>
    {% if result.entropy %}
      <pre>{{ result.entropy }}</pre>
    {% else %}
      <p><i>No entropy output captured.</i></p>
    {% endif %}
  {% endif %}

  {% if result.errors %}
    <div class="error">
      <h3>Errors</h3>
      <pre>{{ result.errors }}</pre>
    </div>
  {% endif %}

  <details>
    <summary>Raw Output</summary>
    <pre>{{ result.raw.stdout }}</pre>
    {% if result.raw.stderr %}
    <pre style="color:#c00">{{ result.raw.stderr }}</pre>
    {% endif %}
  </details>
</div>
"""
)

_HELP_HTML = Template(
    """
<div class="panel">
  <h2>Binwalk – Help</h2>
  <p>Scans binaries for embedded files and signatures, extracts content, and performs entropy analysis.</p>
  <ul>
    <li><b>Signature Scan</b>: <code>binwalk &lt;file&gt;</code></li>
    <li><b>Extract</b>: <code>binwalk -e -C &lt;output_dir&gt; &lt;file&gt;</code> (collects outputs deterministically)</li>
    <li><b>Entropy</b>: <code>binwalk -E &lt;file&gt;</code></li>
    <li>Windows users can rely on WSL; this module auto-detects and calls it.</li>
  </ul>
</div>
"""
)


# =============================
# Feature Implementation
# =============================
def register():
    instance = Feature()

    easy = EasyOptions("Binwalk – Choose an action:")
    easy.add_option("help", "Help / Tips", instance.option_help)
    easy.add_option("scan_html", "Signature Scan (HTML)", instance.option_scan_html)
    easy.add_option("extract_html", "Extract (HTML)", instance.option_extract_html)
    easy.add_option("entropy_html", "Entropy (HTML)", instance.option_entropy_html)
    # Developer-friendly JSON outputs
    easy.add_option("scan_json", "Signature Scan (JSON)", instance.option_scan_json)
    easy.add_option("extract_json", "Extract (JSON)", instance.option_extract_json)
    easy.add_option("entropy_json", "Entropy (JSON)", instance.option_entropy_json)

    return {
        "instance": instance,
        "self_test": instance.self_test,
        "shutdown": instance.shutdown,
        "easy_options": easy,
    }


class Feature(BaseFeature):
    #
    # BaseFeature contract
    #
    def run_default(self, params: dict) -> str:
        # Default to signature scan (HTML)
        return self.option_scan_html(params)

    def self_test(self) -> bool:
        """
        Quick presence check, but do not fail the feature if missing to keep UI usable.
        """
        mode, base_cmd, notes = _detect_runtime()
        return True

    def shutdown(self) -> None:
        print("[binwalk] Shutdown called.")

    #
    # EasyOptions callbacks
    #
    def option_help(self, params: dict) -> str:
        return _HELP_HTML.render()

    def option_scan_html(self, params: dict) -> str:
        res = self._run_scan(params)
        return _HTML_TEMPLATE.render(result=res.to_dict())

    def option_extract_html(self, params: dict) -> str:
        res = self._run_extract(params)
        return _HTML_TEMPLATE.render(result=res.to_dict())

    def option_entropy_html(self, params: dict) -> str:
        res = self._run_entropy(params)
        return _HTML_TEMPLATE.render(result=res.to_dict())

    def option_scan_json(self, params: dict) -> str:
        res = self._run_scan(params)
        return "<pre>" + json.dumps(res.to_dict(), indent=2) + "</pre>"

    def option_extract_json(self, params: dict) -> str:
        res = self._run_extract(params)
        return "<pre>" + json.dumps(res.to_dict(), indent=2) + "</pre>"

    def option_entropy_json(self, params: dict) -> str:
        res = self._run_entropy(params)
        return "<pre>" + json.dumps(res.to_dict(), indent=2) + "</pre>"

    #
    # Core actions
    #
    def _run_scan(self, params: dict) -> BinwalkResult:
        file_path = (params or {}).get("file_path") or ""
        notes: List[str] = []

        if not file_path or not os.path.isfile(file_path):
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="scan",
                file=file_path,
                cmd=[],
                signatures=[],
                output_paths=[],
                entropy=None,
                errors="No file selected or invalid path.",
                raw={"stdout": "", "stderr": ""},
                notes=["Select a valid file first."],
            )

        mode, base_cmd, detect_notes = _detect_runtime()
        notes.extend(detect_notes)
        if not base_cmd:
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="scan",
                file=file_path,
                cmd=[],
                signatures=[],
                output_paths=[],
                entropy=None,
                errors="binwalk runtime not found (native or WSL).",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

        file_arg = _maybe_wsl_path(mode, file_path)
        cmd = base_cmd + [file_arg]

        try:
            proc = _run(cmd, cwd=os.path.dirname(file_path), timeout=120, text=True)
            stdout, stderr = proc.stdout, proc.stderr
            ok = proc.returncode == 0

            if "command not found" in (stderr or "").lower():
                notes.append("binwalk not installed. On Ubuntu: `sudo apt install -y binwalk`.")

            signatures = _parse_signatures(stdout)

            return BinwalkResult(
                tool="binwalk",
                ok=ok,
                action="scan",
                file=file_path,
                cmd=cmd,
                signatures=signatures,
                output_paths=[],
                entropy=None,
                errors=None if ok else (stderr or "Non-zero exit status"),
                raw={"stdout": stdout, "stderr": stderr or ""},
                notes=notes,
            )

        except subprocess.TimeoutExpired:
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="scan",
                file=file_path,
                cmd=cmd,
                signatures=[],
                output_paths=[],
                entropy=None,
                errors="Timeout while running binwalk scan.",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )
        except Exception as e:
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="scan",
                file=file_path,
                cmd=cmd,
                signatures=[],
                output_paths=[],
                entropy=None,
                errors=f"Error running binwalk scan: {e}",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

    def _run_extract(self, params: dict) -> BinwalkResult:
        """
        Extract embedded files.
        Options (via params):
          - output_dir: target directory (default: same folder as file)
          - matryoshka: bool -> add -M (recursive)
        We use `-e` and `-C <output_dir>` so artifacts land predictably.
        """
        file_path = (params or {}).get("file_path") or ""
        notes: List[str] = []

        if not file_path or not os.path.isfile(file_path):
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="extract",
                file=file_path,
                cmd=[],
                signatures=[],
                output_paths=[],
                entropy=None,
                errors="No file selected or invalid path.",
                raw={"stdout": "", "stderr": ""},
                notes=["Select a valid file first."],
            )

        mode, base_cmd, detect_notes = _detect_runtime()
        notes.extend(detect_notes)
        if not base_cmd:
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="extract",
                file=file_path,
                cmd=[],
                signatures=[],
                output_paths=[],
                entropy=None,
                errors="binwalk runtime not found (native or WSL).",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

        # Determine output directory
        default_out = os.path.dirname(os.path.abspath(file_path))
        output_dir = (params or {}).get("output_dir") or default_out
        os.makedirs(output_dir, exist_ok=True)

        # Pre-scan directory state to find newly created paths after extraction
        pre_existing = set(os.listdir(output_dir))

        file_arg = _maybe_wsl_path(mode, file_path)
        out_arg = _maybe_wsl_path(mode, output_dir)

        cmd = base_cmd + ["-e", "-C", out_arg]
        if (params or {}).get("matryoshka"):
            cmd.append("-M")
        cmd.append(file_arg)

        try:
            proc = _run(cmd, cwd=None, timeout=300, text=True)
            stdout, stderr = proc.stdout, proc.stderr
            ok = proc.returncode == 0

            if "command not found" in (stderr or "").lower():
                notes.append("binwalk not installed. On Ubuntu: `sudo apt install -y binwalk`.")

            # Collect created artifacts
            time.sleep(0.2)  # small delay to allow FS to settle
            created = []
            try:
                for name in os.listdir(output_dir):
                    if name not in pre_existing:
                        created.append(os.path.join(output_dir, name))
                # also consider the common "<basename>.extracted" directory
                base = os.path.basename(file_path)
                extracted_dir = os.path.join(output_dir, f"{base}.extracted")
                if os.path.exists(extracted_dir) and extracted_dir not in created:
                    created.append(extracted_dir)
            except Exception:
                pass

            return BinwalkResult(
                tool="binwalk",
                ok=ok,
                action="extract",
                file=file_path,
                cmd=cmd,
                signatures=[],
                output_paths=created,
                entropy=None,
                errors=None if ok else (stderr or "Extraction failed or produced no output"),
                raw={"stdout": stdout, "stderr": stderr or ""},
                notes=notes,
            )

        except subprocess.TimeoutExpired:
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="extract",
                file=file_path,
                cmd=cmd,
                signatures=[],
                output_paths=[],
                entropy=None,
                errors="Timeout while running binwalk extract.",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )
        except Exception as e:
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="extract",
                file=file_path,
                cmd=cmd,
                signatures=[],
                output_paths=[],
                entropy=None,
                errors=f"Error running binwalk extract: {e}",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

    def _run_entropy(self, params: dict) -> BinwalkResult:
        file_path = (params or {}).get("file_path") or ""
        notes: List[str] = []

        if not file_path or not os.path.isfile(file_path):
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="entropy",
                file=file_path,
                cmd=[],
                signatures=[],
                output_paths=[],
                entropy=None,
                errors="No file selected or invalid path.",
                raw={"stdout": "", "stderr": ""},
                notes=["Select a valid file first."],
            )

        mode, base_cmd, detect_notes = _detect_runtime()
        notes.extend(detect_notes)
        if not base_cmd:
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="entropy",
                file=file_path,
                cmd=[],
                signatures=[],
                output_paths=[],
                entropy=None,
                errors="binwalk runtime not found (native or WSL).",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

        file_arg = _maybe_wsl_path(mode, file_path)
        cmd = base_cmd + ["-E", file_arg]

        try:
            proc = _run(cmd, cwd=os.path.dirname(file_path), timeout=180, text=True)
            stdout, stderr = proc.stdout, proc.stderr
            ok = proc.returncode == 0

            if "command not found" in (stderr or "").lower():
                notes.append("binwalk not installed. On Ubuntu: `sudo apt install -y binwalk`.")

            return BinwalkResult(
                tool="binwalk",
                ok=ok,
                action="entropy",
                file=file_path,
                cmd=cmd,
                signatures=[],
                output_paths=[],
                entropy=stdout if ok else None,
                errors=None if ok else (stderr or "Non-zero exit status"),
                raw={"stdout": stdout, "stderr": stderr or ""},
                notes=notes,
            )

        except subprocess.TimeoutExpired:
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="entropy",
                file=file_path,
                cmd=cmd,
                signatures=[],
                output_paths=[],
                entropy=None,
                errors="Timeout while running binwalk entropy.",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )
        except Exception as e:
            return BinwalkResult(
                tool="binwalk",
                ok=False,
                action="entropy",
                file=file_path,
                cmd=cmd,
                signatures=[],
                output_paths=[],
                entropy=None,
                errors=f"Error running binwalk entropy: {e}",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )
