from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from jinja2 import Template
from app.core.contracts.feature_interface import BaseFeature
from app.core.easy_options import EasyOptions

# Optional: tiny prompt for channel (and for future params) if UI has no inputs yet
try:
    import tkinter as _tk
    from tkinter import simpledialog as _simpledialog
except Exception:
    _tk = None
    _simpledialog = None


# -----------------------------
# Normalized result structure
# -----------------------------
@dataclass
class ZstegResult:
    tool: str
    ok: bool
    action: str  # "scan" | "extract"
    file: str
    cmd: List[str]
    findings: List[Dict[str, str]]  # parsed highlights (best-effort)
    output_files: List[str]         # files we created (extract)
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
            "findings": self.findings,
            "output_files": self.output_files,
            "errors": self.errors,
            "raw": self.raw,
            "notes": self.notes,
        }


# -----------------------------
# Helpers (platform / exec)
# -----------------------------
def _is_windows() -> bool:
    return platform.system() == "Windows"


def _detect_runtime() -> Tuple[str, Optional[List[str]], List[str]]:
    """
    Returns (mode, base_cmd, notes)
    mode: "native" | "wsl" | "unix" | "missing"
    base_cmd: list like ["zsteg"] or ["wsl", "-e", "zsteg"]
    """
    notes: List[str] = []
    if _is_windows():
        exe = shutil.which("zsteg")
        if exe:
            return "native", [exe], notes
        if shutil.which("wsl"):
            notes.append("Using WSL fallback for zsteg (Ruby gem).")
            return "wsl", ["wsl", "-e", "zsteg"], notes
        notes.append("zsteg not found on PATH and WSL not available.")
        notes.append("Hint: zsteg is a Ruby gem. Install Ruby then `gem install zsteg`.")
        return "missing", None, notes
    else:
        exe = shutil.which("zsteg")
        if exe:
            return "unix", [exe], notes
        notes.append("zsteg not found on PATH.")
        notes.append("Hint: zsteg is a Ruby gem. Install Ruby then `gem install zsteg`.")
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


def _run(cmd: List[str], cwd: Optional[str] = None, timeout: int = 90, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=text,
        timeout=timeout,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        shell=False,
    )


# -----------------------------
# Parsers / prompts
# -----------------------------
def _parse_findings(stdout: str) -> List[Dict[str, str]]:
    """
    Best-effort parser to surface likely interesting lines from zsteg -a output.
    We keep it lenient to accommodate many zsteg formats.
    """
    findings: List[Dict[str, str]] = []
    for line in stdout.splitlines():
        # Common patterns: "b1,r,lsb,xy .. text: 'FLAG{..}'"
        m = re.match(r"\s*([a-z0-9_,]+)\s+\.\.\s+(.*)$", line, re.IGNORECASE)
        if m:
            findings.append({"channel": m.group(1), "desc": m.group(2)})
            continue

        # Another common shape: "b1,r,msb,xy: something"
        m = re.match(r"\s*([a-z0-9_,]+)\s*:\s*(.+)$", line, re.IGNORECASE)
        if m and "," in m.group(1):
            findings.append({"channel": m.group(1), "desc": m.group(2)})
            continue

        # Lines mentioning text/strings or compressed data
        if any(key in line.lower() for key in ("text:", "utf", "ascii", "zlib", "bzip", "gzip", "png", "pcx", "string")):
            findings.append({"channel": "", "desc": line.strip()})
    return findings


def _prompt(title: str, prompt: str) -> str:
    if _tk is None or _simpledialog is None:
        return ""
    try:
        root = _tk.Tk()
        root.withdraw()
        val = _simpledialog.askstring(title, prompt)
        root.destroy()
        return val or ""
    except Exception:
        return ""


_HTML_TEMPLATE = Template(
    """
<div class="panel">
  <h2>Zsteg – {{ result.action|capitalize }} ({{ "OK" if result.ok else "Failed" }})</h2>
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
    <h3>Findings</h3>
    {% if result.findings %}
      <table class="kv">
        <thead><tr><th>Channel</th><th>Description</th></tr></thead>
        <tbody>
        {% for f in result.findings %}
          <tr><td>{{ f.channel }}</td><td>{{ f.desc }}</td></tr>
        {% endfor %}
        </tbody>
      </table>
    {% else %}
      <p><i>No findings highlighted. Check raw output below.</i></p>
    {% endif %}
  {% endif %}

  {% if result.action == "extract" %}
    <h3>Output Files</h3>
    {% if result.output_files %}
      <ul>
      {% for p in result.output_files %}
        <li><code>{{ p }}</code></li>
      {% endfor %}
      </ul>
    {% else %}
      <p><i>No output produced.</i></p>
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
  <h2>Zsteg – Help</h2>
  <p>Scans PNG/BMP (and related) images for LSB steganography using <code>zsteg</code> (Ruby gem).</p>
  <ul>
    <li><b>Scan</b> runs <code>zsteg -a &lt;file&gt;</code> and highlights likely hits.</li>
    <li><b>Extract</b> runs <code>zsteg -E &lt;channel&gt; &lt;file&gt;</code> and saves the bytes to disk.</li>
    <li>If your input isn’t PNG/BMP, consider converting first (e.g., <code>convert input.jpg output.png</code>).</li>
    <li>Windows without native Ruby can use WSL; this module auto-detects and calls it.</li>
    <li>Install tip: <code>gem install zsteg</code></li>
  </ul>
</div>
"""
)


# =============================
# Feature Implementation
# =============================
def register():
    instance = Feature()

    easy = EasyOptions("Zsteg – Choose an action:")
    easy.add_option("help", "Help / Tips", instance.option_help)
    easy.add_option("scan_html", "Scan (HTML)", instance.option_scan_html)
    easy.add_option("extract_html", "Extract (HTML)", instance.option_extract_html)
    # Developer-friendly JSON outputs
    easy.add_option("scan_json", "Scan (JSON)", instance.option_scan_json)
    easy.add_option("extract_json", "Extract (JSON)", instance.option_extract_json)

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
        # Default to Scan (HTML)
        return self.option_scan_html(params)

    def self_test(self) -> bool:
        """
        Quick presence check, but do not fail the feature if missing.
        Users can still read Help or use WSL/native later.
        """
        mode, base_cmd, notes = _detect_runtime()
        return True

    def shutdown(self) -> None:
        print("[zsteg] Shutdown called.")

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

    def option_scan_json(self, params: dict) -> str:
        res = self._run_scan(params)
        return "<pre>" + json.dumps(res.to_dict(), indent=2) + "</pre>"

    def option_extract_json(self, params: dict) -> str:
        res = self._run_extract(params)
        return "<pre>" + json.dumps(res.to_dict(), indent=2) + "</pre>"

    #
    # Core actions
    #
    def _run_scan(self, params: dict) -> ZstegResult:
        file_path = (params or {}).get("file_path") or ""
        notes: List[str] = []

        if not file_path or not os.path.isfile(file_path):
            return ZstegResult(
                tool="zsteg",
                ok=False,
                action="scan",
                file=file_path,
                cmd=[],
                findings=[],
                output_files=[],
                errors="No file selected or invalid path.",
                raw={"stdout": "", "stderr": ""},
                notes=["Select a valid file first."],
            )

        # Detect runtime
        mode, base_cmd, detect_notes = _detect_runtime()
        notes.extend(detect_notes)
        if not base_cmd:
            return ZstegResult(
                tool="zsteg",
                ok=False,
                action="scan",
                file=file_path,
                cmd=[],
                findings=[],
                output_files=[],
                errors="zsteg runtime not found (native or WSL).",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

        file_arg = _maybe_wsl_path(mode, file_path)
        cmd = base_cmd + ["-a", file_arg]  # aggressive scan

        try:
            # Non-interactive; capture text output
            proc = _run(cmd, cwd=os.path.dirname(file_path), timeout=120, text=True)
            stdout, stderr = proc.stdout, proc.stderr
            ok = proc.returncode == 0

            # Add helpful notes
            if ("unknown file type" in (stdout + stderr).lower()) or ("not supported" in (stdout + stderr).lower()):
                notes.append("Input may not be PNG/BMP; consider converting (e.g., `convert input.jpg output.png`).")
            if "command not found" in (stderr.lower()):
                notes.append("zsteg not installed. Install Ruby and `gem install zsteg`.")

            findings = _parse_findings(stdout)

            return ZstegResult(
                tool="zsteg",
                ok=ok,
                action="scan",
                file=file_path,
                cmd=cmd,
                findings=findings,
                output_files=[],
                errors=None if ok else (stderr or "Non-zero exit status"),
                raw={"stdout": stdout, "stderr": stderr},
                notes=notes,
            )

        except subprocess.TimeoutExpired:
            return ZstegResult(
                tool="zsteg",
                ok=False,
                action="scan",
                file=file_path,
                cmd=cmd,
                findings=[],
                output_files=[],
                errors="Timeout while running zsteg scan.",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )
        except Exception as e:
            return ZstegResult(
                tool="zsteg",
                ok=False,
                action="scan",
                file=file_path,
                cmd=cmd,
                findings=[],
                output_files=[],
                errors=f"Error running zsteg scan: {e}",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

    def _run_extract(self, params: dict) -> ZstegResult:
        """
        Extract bytes from a given channel.
        - If params['channel'] provided, use it; else prompt (if tkinter available).
        - Writes to <same folder>/zsteg_extract.bin unless params['output_name'] provided.
        """
        file_path = (params or {}).get("file_path") or ""
        notes: List[str] = []

        if not file_path or not os.path.isfile(file_path):
            return ZstegResult(
                tool="zsteg",
                ok=False,
                action="extract",
                file=file_path,
                cmd=[],
                findings=[],
                output_files=[],
                errors="No file selected or invalid path.",
                raw={"stdout": "", "stderr": ""},
                notes=["Select a valid file first."],
            )

        # Detect runtime
        mode, base_cmd, detect_notes = _detect_runtime()
        notes.extend(detect_notes)
        if not base_cmd:
            return ZstegResult(
                tool="zsteg",
                ok=False,
                action="extract",
                file=file_path,
                cmd=[],
                findings=[],
                output_files=[],
                errors="zsteg runtime not found (native or WSL).",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

        # Get channel from params or prompt
        channel = (params or {}).get("channel") or ""
        if not channel:
            channel = _prompt("Zsteg Extract", "Enter channel (e.g., b1,r,lsb,xy):")
        channel = (channel or "").strip()

        if not channel:
            notes.append("No channel specified; extraction skipped.")
            return ZstegResult(
                tool="zsteg",
                ok=False,
                action="extract",
                file=file_path,
                cmd=[],
                findings=[],
                output_files=[],
                errors="Missing channel for extraction.",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

        out_dir = os.path.dirname(os.path.abspath(file_path))
        out_name = (params or {}).get("output_name") or "zsteg_extract.bin"
        out_path = os.path.join(out_dir, out_name)

        file_arg = _maybe_wsl_path(mode, file_path)

        # zsteg -E prints bytes to stdout -> we save them ourselves
        cmd = base_cmd + ["-E", channel, file_arg]

        try:
            proc = _run(cmd, cwd=os.path.dirname(file_path), timeout=120, text=False)
            stdout_bytes = proc.stdout or b""
            stderr = proc.stderr.decode("utf-8", errors="ignore") if proc.stderr else ""
            ok = (proc.returncode == 0) and (len(stdout_bytes) > 0)

            if ok:
                try:
                    with open(out_path, "wb") as f:
                        f.write(stdout_bytes)
                except Exception as werr:
                    return ZstegResult(
                        tool="zsteg",
                        ok=False,
                        action="extract",
                        file=file_path,
                        cmd=cmd,
                        findings=[],
                        output_files=[],
                        errors=f"Extraction produced bytes but writing file failed: {werr}",
                        raw={"stdout": f"<{len(stdout_bytes)} bytes>", "stderr": stderr},
                        notes=notes,
                    )

            # Hints
            if ("unknown file type" in stderr.lower()) or ("not supported" in stderr.lower()):
                notes.append("Input may not be PNG/BMP; consider converting (e.g., `convert input.jpg output.png`).")
            if "command not found" in stderr.lower():
                notes.append("zsteg not installed. Install Ruby and `gem install zsteg`.")

            return ZstegResult(
                tool="zsteg",
                ok=ok,
                action="extract",
                file=file_path,
                cmd=cmd,
                findings=[],
                output_files=[out_path] if ok else [],
                errors=None if ok else (stderr or "No bytes produced or non-zero exit"),
                raw={"stdout": f"<{len(stdout_bytes)} bytes>" if stdout_bytes else "", "stderr": stderr},
                notes=notes,
            )

        except subprocess.TimeoutExpired:
            return ZstegResult(
                tool="zsteg",
                ok=False,
                action="extract",
                file=file_path,
                cmd=cmd,
                findings=[],
                output_files=[],
                errors="Timeout while running zsteg extract.",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )
        except Exception as e:
            return ZstegResult(
                tool="zsteg",
                ok=False,
                action="extract",
                file=file_path,
                cmd=cmd,
                findings=[],
                output_files=[],
                errors=f"Error running zsteg extract: {e}",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )
