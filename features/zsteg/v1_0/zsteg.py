# Zsteg Feature — Module Documentation
#
# Purpose:
# Automates detection and extraction of LSB-style steganography in PNG/BMP (and related) images using the zsteg Ruby gem.
# Exposes quick actions via EasyOptions and returns a normalized result for consistent HTML/JSON rendering across tools.
#
# Architecture & Modularity:
# - Feature(BaseFeature): Implements the feature contract for FeatureManager. Provides EasyOptions callbacks and a sensible default action.
# - ZstegResult (dataclass): Normalized container for output (action, ok, cmd, findings, output_files, raw, notes). Exposed via to_dict().
# - Templating: Uses jinja2.Template for HTML panels (Scan/Extract results) and Help panel.
#
# Contracts used:
# - app.core.contracts.feature_interface.BaseFeature
# - app.core.easy_options.EasyOptions
#
# Modularity:
# - Plug-in style: register() returns { instance, self_test, shutdown, easy_options }.
# - Stateless execution: inputs are passed via params: dict (e.g., file_path, optionally channel, output_name).
#
# Platform Awareness & External Dependencies:
# - Binary: zsteg (Ruby gem).
# - Windows native: uses zsteg if found in PATH.
# - Windows fallback: if not found, uses WSL (wsl -e zsteg) and converts paths to /mnt/....
# - Linux/macOS: executes zsteg directly.
# - If neither native nor WSL is available, the feature returns a graceful error with install hints.
#
# Commands Executed:
# - Scan: zsteg -a <file> (aggressive scan). Output is parsed to surface likely hits (channels + short description), while the full raw output is preserved.
# - Extract: zsteg -E <channel> <file> (bytes on stdout; module writes to disk). If no channel is provided in params, a tiny tkinter prompt asks for one (if available). Output is saved as zsteg_extract.bin next to the input (or to params["output_name"] if given).
#
# EasyOptions (UI):
# Option ID      Label           Action
# help           Help / Tips     Shows usage tips and install guidance
# scan_html      Scan (HTML)     Runs zsteg -a, renders HTML
# extract_html   Extract (HTML)  Runs zsteg -E, renders HTML
# scan_json      Scan (JSON)     Returns normalized dict as JSON
# extract_json   Extract (JSON)  Returns normalized dict as JSON
# - run_default() calls Scan (HTML).
#
# Normalized Result Schema:
# {
#   "tool": "zsteg",
#   "ok": true,
#   "action": "scan",                    # or "extract"
#   "file": "C:/path/image.png",
#   "cmd": ["zsteg","-a","/mnt/c/path/image.png"],
#   "findings": [
#     {"channel": "b1,r,lsb,xy", "desc": "text: 'FLAG{...}'"},
#     {"channel": "", "desc": "zlib: ..."}
#   ],
#   "output_files": [],                  # e.g., ["C:/path/zsteg_extract.bin"] for extract
#   "errors": null,
#   "raw": { "stdout": "...", "stderr": "" },
#   "notes": [
#     "Using WSL fallback for zsteg (Ruby gem).",
#     "Input may not be PNG/BMP; consider converting (e.g., `convert input.jpg output.png`)."
#   ]
# }
#
# - findings are best-effort: the parser highlights common zsteg patterns but the complete raw output is always included.
#
# Error Handling & Hints:
# - Missing binary: Clear message + hint to install Ruby and gem install zsteg, or use WSL.
# - Unsupported/unknown file type: Suggests converting (e.g., JPEG → PNG) before scanning.
# - Timeouts & non-zero exit: Reported with preserved stdout/stderr.
# - Extraction write failures: Surfaces write error and keeps the captured byte length in raw.
#
# Self-test & Shutdown:
# - self_test(): Lightweight presence check (always returns True) so the feature loads even if zsteg isn’t installed; Help remains accessible.
# - shutdown(): No persistent state; logs a message.
#
# Known Limitations:
# - zsteg focuses on PNG/BMP families; other formats may produce limited/unsupported output.
# - Channel discovery still requires human judgment; the module offers a prompt but cannot “guess” the correct channel.
# - On Windows without Ruby/WSL, actions will fail gracefully with guidance.
#
# Integration Points:
# - Works with the existing web UI: pywebview.api.run_feature("zsteg", option); returns HTML (or JSON variants).
# - Normalized dict enables aggregating Zsteg results with other features in a consistent


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

# Optional: tiny prompt for channel (if UI has no inputs yet)
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


def _has_file_cmd() -> bool:
    """Detect presence of Unix 'file' tool (needed by zsteg unless --no-file)."""
    return shutil.which("file") is not None


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
            # If native zsteg is present but no 'file', we can still run with --no-file
            if not _has_file_cmd():
                notes.append("Native zsteg without 'file' detected; will use --no-file.")
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
# Parsers / prompts / errors
# -----------------------------
def _parse_findings(stdout: str) -> List[Dict[str, str]]:
    """
    Best-effort parser to surface likely interesting lines from zsteg -a output.
    """
    findings: List[Dict[str, str]] = []
    for line in stdout.splitlines():
        # "b1,r,lsb,xy .. text: 'FLAG{..}'"
        m = re.match(r"\s*([a-z0-9_,]+)\s+\.\.\s+(.*)$", line, re.IGNORECASE)
        if m:
            findings.append({"channel": m.group(1), "desc": m.group(2)})
            continue
        # "b1,r,msb,xy: something"
        m = re.match(r"\s*([a-z0-9_,]+)\s*:\s*(.+)$", line, re.IGNORECASE)
        if m and "," in m.group(1):
            findings.append({"channel": m.group(1), "desc": m.group(2)})
            continue
        # Generic interesting hints
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


def _sanitize_stderr(err: str, limit_lines: int = 10, limit_chars: int = 800) -> str:
    """
    Strip Ruby backtrace noise and trim size so users don't see scary internals.
    """
    if not err:
        return ""
    lines = []
    for ln in err.splitlines():
        # Drop stack frames & noisy "from ..." lines
        if re.search(r"(ruby[/\\]gems|\bzsteg[/\\].*\.rb:|\bopen3\.rb:|lib[/\\]ruby)", ln, re.IGNORECASE):
            continue
        if ln.strip().startswith("from "):
            continue
        lines.append(ln)
        if len(lines) >= limit_lines:
            break
    msg = "\n".join(lines).strip()
    if len(msg) > limit_chars:
        msg = msg[:limit_chars] + "…"
    return msg


def _suggest_channels(file_path: str, mode: str, base_cmd: List[str]) -> List[str]:
    """
    Run a quick zsteg -a to collect plausible channel tokens.
    """
    file_arg = _maybe_wsl_path(mode, file_path)
    cmd = list(base_cmd)
    # Inject --no-file if native Windows without 'file'
    if _is_windows() and mode == "native" and not _has_file_cmd():
        cmd += ["--no-file"]
    cmd += ["-a", file_arg]
    try:
        proc = _run(cmd, cwd=os.path.dirname(file_path), timeout=60, text=True)
        chans: List[str] = []
        for f in _parse_findings(proc.stdout):
            ch = f.get("channel", "").strip()
            if ch and ch not in chans:
                chans.append(ch)
            if len(chans) >= 8:
                break
        return chans
    except Exception:
        return []


def _friendly_error(stderr: str, stdout: str, file_path: str, mode: str, base_cmd: List[str], attempted_channel: str = "") -> Tuple[str, List[str]]:
    """
    Convert raw Ruby errors into a concise, actionable message.
    Returns (friendly_message, extra_notes)
    """
    s = (stderr or "") + "\n" + (stdout or "")
    s_low = s.lower()

    # Missing external 'file' (native Windows without MSYS2/WSL)
    if "no such file or directory - file -n -b -f -" in s_low:
        return (
            "zsteg couldn't call the external 'file' tool. Either install MSYS2 'file' or run with --no-file.",
            ["MSYS2 tip: install 'file' and add C:\\msys64\\usr\\bin to PATH.", "This module auto-adds --no-file on Windows when 'file' is missing."]
        )

    # Invalid/unsupported channel → ColorExtractor nil error
    if "color_extractor" in s_low or "undefined method `size' for nil" in s_low:
        notes = ["The channel you provided isn't valid for this image. Use a channel reported by 'zsteg -a'."]
        chans = _suggest_channels(file_path, mode, base_cmd)
        if chans:
            notes.append("Suggested channels: " + ", ".join(chans[:5]))
        if attempted_channel:
            notes.append(f"Attempted channel: {attempted_channel}")
        return ("Invalid channel for this image. Pick one from a scan and try again.", notes)

    # Generic not supported / unknown file type
    if "unknown file type" in s_low or "not supported" in s_low:
        return (
            "This format may not be supported by zsteg. Convert to PNG/BMP and retry.",
            ["Example: convert input.jpg output.png"]
        )

    # Fallback
    return (_sanitize_stderr(stderr) or "Extraction failed.", [])


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
    <summary>Raw Output (sanitized)</summary>
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
    <li>Windows without native 'file' automatically uses <code>--no-file</code>.</li>
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
        # Keep UI usable even if zsteg isn't present
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

        # Build command with --no-file if needed on native Windows
        cmd = list(base_cmd)
        if _is_windows() and mode == "native" and not _has_file_cmd():
            cmd += ["--no-file"]
        cmd += ["-a", file_arg]

        try:
            proc = _run(cmd, cwd=os.path.dirname(file_path), timeout=120, text=True)
            stdout, stderr = proc.stdout, proc.stderr
            ok = proc.returncode == 0

            # Friendly errors / notes
            if "command not found" in (stderr or "").lower():
                notes.append("zsteg not installed. Install Ruby and `gem install zsteg`.")
            if ("unknown file type" in (stdout + stderr).lower()) or ("not supported" in (stdout + stderr).lower()):
                notes.append("Input may not be PNG/BMP; consider converting (e.g., `convert input.jpg output.png`).")

            findings = _parse_findings(stdout)

            return ZstegResult(
                tool="zsteg",
                ok=ok,
                action="scan",
                file=file_path,
                cmd=cmd,
                findings=findings,
                output_files=[],
                errors=None if ok else (_sanitize_stderr(stderr) or "Non-zero exit status"),
                raw={"stdout": stdout, "stderr": _sanitize_stderr(stderr)},
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

        # Build command with --no-file if needed
        cmd = list(base_cmd)
        if _is_windows() and mode == "native" and not _has_file_cmd():
            cmd += ["--no-file"]
        cmd += ["-E", channel, file_arg]

        try:
            proc = _run(cmd, cwd=os.path.dirname(file_path), timeout=120, text=False)
            stdout_bytes = proc.stdout or b""
            stderr_text = proc.stderr.decode("utf-8", errors="ignore") if proc.stderr else ""
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
                        raw={"stdout": f"<{len(stdout_bytes)} bytes>", "stderr": _sanitize_stderr(stderr_text)},
                        notes=notes,
                    )

            if not ok:
                # Make a friendly message and add suggestions
                friendly_msg, extra_notes = _friendly_error(stderr_text, "", file_path, mode, base_cmd, attempted_channel=channel)
                notes.extend(extra_notes)

            return ZstegResult(
                tool="zsteg",
                ok=ok,
                action="extract",
                file=file_path,
                cmd=cmd,
                findings=[],
                output_files=[out_path] if ok else [],
                errors=None if ok else friendly_msg,
                raw={"stdout": f"<{len(stdout_bytes)} bytes>" if stdout_bytes else "", "stderr": _sanitize_stderr(stderr_text)},
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
