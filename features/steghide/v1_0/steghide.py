# Steghide Feature — Module Documentation
#
# Purpose:
# Automates inspection and extraction of steganographic payloads hidden in cover files supported by steghide (JPEG, BMP3, WAV, AU).
# Exposes a UI via EasyOptions and returns a normalized result for consistent HTML/JSON rendering.
#
# Architecture & Modularity:
# - Feature(BaseFeature): Implements the feature contract for FeatureManager. Provides EasyOptions callbacks and default behavior.
# - SteghideResult (dataclass): Internal normalized container for results (action, success, parsed info, extracted paths, raw stdout/stderr, etc.). Exposed as dict via to_dict().
# - Templating: Uses jinja2.Template for HTML rendering of Info/Extract results and Help panel.
#
# Contracts used:
# - app.core.contracts.feature_interface.BaseFeature
# - app.core.easy_options.EasyOptions
#
# Modularity:
# - Fully plug-in driven: register() returns the instance, optional self_test, shutdown, and EasyOptions menu.
# - No global state; all actions accept a params: dict for inputs (uses params["file_path"]).
#
# External Dependencies & Platform Awareness:
# - Binary: steghide (native binary on Linux/macOS or steghide.exe on Windows).
# - Windows fallback: Uses WSL (wsl -e steghide) if no native binary is found.
# - Path conversion: Windows paths (C:\…) mapped to /mnt/c/… for WSL.
# - Non-interactive: Always passes -p <passphrase> to prevent interactive prompts.
#
# Commands Executed:
# - Info: steghide info -v -sf <file> -p <passphrase> (parses Key: Value lines from stdout)
# - Extract: steghide extract -sf <file> -xf <output_file> -f -p <passphrase> (writes steghide_extracted.bin next to input)
# - Passphrase: Collected via tkinter prompt (masked); falls back to empty passphrase if unavailable.
#
# EasyOptions (UI):
# Option ID         Label                 Action
# help              Help / Tips           Shows usage tips & BMP3 note
# info_html         Info (HTML)           Runs info, renders HTML
# extract_html      Extract (HTML)        Runs extract, renders HTML
# info_json         Info (JSON)           Returns normalized dict as JSON
# extract_json      Extract (JSON)        Returns normalized dict as JSON
# - run_default() calls Info (HTML) for simple click behavior.
#
# Normalized Result Schema:
# {
#   "tool": "steghide",
#   "ok": true,
#   "action": "info",                # or "extract"
#   "file": "C:/path/to/cover.bmp",
#   "cmd": ["steghide","info","-v","-sf","/mnt/c/path/to/cover.bmp","-p","*****"],
#   "info": {                        # parsed Key: Value lines from `info -v`
#     "encryption": "rijndael-128",  # fields vary by file; best-effort parse
#     "compression": "9",
#     "embedded file name": "secret.txt",
#     "embedded file size": "123 bytes"
#   },
#   "extracted": ["C:/path/to/steghide_extracted.bin"],  # only for extract
#   "errors": null,                # stderr or message on failure
#   "raw": {
#     "stdout": "...",
#     "stderr": ""
#   },
#   "notes": [
#     "Using WSL fallback for steghide.",
#     "BMP V5 detected; convert to BMP3: convert input.bmp bmp3:output_v3.bmp"
#   ]
# }
#
# - Info fields are best-effort and depend on steghide output (encryption, compression, embedded file name/size, cipher, etc.).
#
# Error Handling & Hints:
# - Missing binary: Returns ok=false with a clear note (suggests using WSL or installing steghide).
# - Unsupported BMP V5 (biSize: 124): Adds a hint to convert to BMP3 (ImageMagick).
# - Wrong/empty passphrase or no payload: Adds a hint based on common steghide messages.
# - Timeouts: Clear timeouts for both actions.
# - Raw output: Full stdout/stderr provided under a collapsible block for debugging.
#
# Self-test & Shutdown:
# - self_test(): Non-blocking (always returns True) so the feature can load even when steghide/WSL isn’t present; users can still read Help.
# - shutdown(): Logs a simple message; no persistent state to clean up.
#
# Security Notes:
# - Passphrase is passed via -p (visible in process args on the local machine). Acceptable for CTF tooling; for stricter handling, use a temp file or env var.
#
# Known Limitations:
# - Info parsing is line-based and tolerant, but not a strict schema; fields depend on steghide’s output.
# - BMP V5 needs conversion to BMP3 for Steghide compatibility.
# - On Windows without WSL or a native binary, the action will gracefully fail with guidance.
#
# Integration Points:
# - Works with the existing web UI: frontend calls api.run_feature("steghide", option); module returns HTML/JSON strings.
# - Normalized dict makes it easy to aggregate results or switch renderer



from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# UI/Templating + Feature protocol
from jinja2 import Template
from app.core.contracts.feature_interface import BaseFeature
from app.core.easy_options import EasyOptions

# Optional: tiny prompt for passphrase (non-blocking in pywebview context)
try:
    import tkinter as _tk
    from tkinter import simpledialog as _simpledialog
except Exception:  # headless or unavailable
    _tk = None
    _simpledialog = None


# -----------------------------
# Normalized result structure
# -----------------------------
@dataclass
class SteghideResult:
    tool: str
    ok: bool
    action: str  # "info" | "extract"
    file: str
    cmd: List[str]
    info: Dict[str, str]
    extracted: List[str]
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
            "info": self.info,
            "extracted": self.extracted,
            "errors": self.errors,
            "raw": self.raw,
            "notes": self.notes,
        }


# -----------------------------
# Helpers
# -----------------------------
def _is_windows() -> bool:
    return platform.system() == "Windows"


def _detect_runtime() -> Tuple[str, Optional[List[str]], List[str]]:
    """
    Returns (mode, base_cmd, notes)
    mode: "native" | "wsl" | "unix" | "missing"
    base_cmd: list like ["steghide"] or ["wsl", "-e", "steghide"]
    """
    notes: List[str] = []
    if _is_windows():
        exe = shutil.which("steghide.exe") or shutil.which("steghide")
        if exe:
            return "native", [exe], notes
        # fallback to WSL
        if shutil.which("wsl"):
            notes.append("Using WSL fallback for steghide.")
            return "wsl", ["wsl", "-e", "steghide"], notes
        notes.append("steghide not found on PATH and WSL not available.")
        return "missing", None, notes
    else:
        exe = shutil.which("steghide")
        if exe:
            return "unix", [exe], notes
        notes.append("steghide not found on PATH.")
        return "missing", None, notes


def _to_wsl_path(win_path: str) -> str:
    """
    Convert 'C:\\path\\to\\file' -> '/mnt/c/path/to/file' for WSL calls.
    """
    drive, rest = os.path.splitdrive(win_path)
    drive_letter = drive.replace(":", "").lower()
    path = rest.replace("\\", "/")
    return f"/mnt/{drive_letter}{path}"


def _maybe_wsl_path(mode: str, p: str) -> str:
    if mode == "wsl" and _is_windows():
        return _to_wsl_path(os.path.abspath(p))
    return p


def _run(cmd: List[str], cwd: Optional[str] = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        shell=False,
    )


def _parse_keyvals(text: str) -> Dict[str, str]:
    """
    Parse common 'Key: Value' lines from steghide info -v output.
    """
    info: Dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"\s*([^:]+)\s*:\s*(.+)\s*$", line)
        if m:
            k = m.group(1).strip()
            v = m.group(2).strip()
            info[k] = v
    return info


def _prompt_passphrase(title="Steghide", prompt="Enter passphrase (leave blank for none):") -> str:
    if _tk is None or _simpledialog is None:
        return ""
    try:
        root = _tk.Tk()
        root.withdraw()
        pw = _simpledialog.askstring(title, prompt, show="*")
        root.destroy()
        return pw or ""
    except Exception:
        return ""


_HTML_TEMPLATE = Template(
    """
<div class="panel">
  <h2>Steghide – {{ result.action|capitalize }} ({{ "OK" if result.ok else "Failed" }})</h2>
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

  {% if result.action == "info" %}
    <h3>Info</h3>
    {% if result.info %}
      <table class="kv">
        <tbody>
        {% for k, v in result.info.items() %}
          <tr><td>{{ k }}</td><td>{{ v }}</td></tr>
        {% endfor %}
        </tbody>
      </table>
    {% else %}
      <p><i>No structured info parsed.</i></p>
    {% endif %}
  {% endif %}

  {% if result.action == "extract" %}
    <h3>Extracted Files</h3>
    {% if result.extracted %}
      <ul>
      {% for p in result.extracted %}
        <li><code>{{ p }}</code></li>
      {% endfor %}
      </ul>
    {% else %}
      <p><i>No files extracted.</i></p>
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
  <h2>Steghide – Help</h2>
  <p>This module inspects and extracts steganographic payloads using <code>steghide</code>.</p>
  <ul>
    <li><b>Info</b> runs <code>steghide info -v</code> and parses key-value metadata.</li>
    <li><b>Extract</b> runs <code>steghide extract</code> and writes the payload to the same folder.</li>
    <li>If your BMP is V5 and unsupported, convert to BMP3:<br>
      <code>convert input.bmp bmp3:output_v3.bmp</code> (ImageMagick)
    </li>
    <li>Windows users without a native steghide can use WSL; this module detects and calls it automatically.</li>
  </ul>
</div>
"""
)


# =============================
# Feature Implementation
# =============================
def register():
    instance = Feature()

    easy = EasyOptions("Steghide – Choose an action:")
    easy.add_option("help", "Help / Tips", instance.option_help)
    easy.add_option("info_html", "Info (HTML)", instance.option_info_html)
    easy.add_option("extract_html", "Extract (HTML)", instance.option_extract_html)
    # For developers who want the normalized dict, we also expose JSON-rendered variants
    easy.add_option("info_json", "Info (JSON)", instance.option_info_json)
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
        # Default to Info (HTML) so clicking the feature does something meaningful
        return self.option_info_html(params)

    def self_test(self) -> bool:
        """
        Keep it quick: verify we can locate a runtime.
        Do NOT fail the whole feature if missing; users on Windows can still click Help.
        """
        mode, base_cmd, notes = _detect_runtime()
        # If completely missing, still return True so the feature loads, but we leave a note
        return True

    def shutdown(self) -> None:
        print("[steghide] Shutdown called.")

    #
    # EasyOptions callbacks
    #
    def option_help(self, params: dict) -> str:
        return _HELP_HTML.render()

    def option_info_html(self, params: dict) -> str:
        res = self._run_info(params)
        return _HTML_TEMPLATE.render(result=res.to_dict())

    def option_extract_html(self, params: dict) -> str:
        res = self._run_extract(params)
        return _HTML_TEMPLATE.render(result=res.to_dict())

    def option_info_json(self, params: dict) -> str:
        res = self._run_info(params)
        return "<pre>" + json.dumps(res.to_dict(), indent=2) + "</pre>"

    def option_extract_json(self, params: dict) -> str:
        res = self._run_extract(params)
        return "<pre>" + json.dumps(res.to_dict(), indent=2) + "</pre>"

    #
    # Core actions
    #
    def _run_info(self, params: dict) -> SteghideResult:
        file_path = (params or {}).get("file_path") or ""
        notes: List[str] = []

        if not file_path or not os.path.isfile(file_path):
            return SteghideResult(
                tool="steghide",
                ok=False,
                action="info",
                file=file_path,
                cmd=[],
                info={},
                extracted=[],
                errors="No file selected or invalid path.",
                raw={"stdout": "", "stderr": ""},
                notes=["Select a valid file first."],
            )

        # Detect runtime
        mode, base_cmd, detect_notes = _detect_runtime()
        notes.extend(detect_notes)
        if not base_cmd:
            return SteghideResult(
                tool="steghide",
                ok=False,
                action="info",
                file=file_path,
                cmd=[],
                info={},
                extracted=[],
                errors="steghide runtime not found (native or WSL).",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

        # Optional passphrase (prompt)
        pw = _prompt_passphrase(title="Steghide Info", prompt="Enter passphrase (leave blank for none):")

        file_arg = _maybe_wsl_path(mode, file_path)
        cmd = base_cmd + ["info", "-v", "-sf", file_arg]
        # Always pass -p to prevent interactive prompts
        cmd += ["-p", pw]

        try:
            proc = _run(cmd, cwd=os.path.dirname(file_path))
            stdout, stderr = proc.stdout, proc.stderr

            info = _parse_keyvals(stdout)
            ok = proc.returncode == 0

            # Detect common issues and add hints
            if "has a format that is not supported" in stdout or "biSize: 124" in stdout or "biSize: 124" in stderr:
                notes.append("BMP V5 detected; convert to BMP3: convert input.bmp bmp3:output_v3.bmp")

            if not ok and ("could not extract any data" in stdout or "wrong passphrase" in stdout.lower()):
                notes.append("Possible wrong/empty passphrase or no embedded payload.")

            return SteghideResult(
                tool="steghide",
                ok=ok,
                action="info",
                file=file_path,
                cmd=cmd,
                info=info,
                extracted=[],
                errors=None if ok else (stderr or "Non-zero exit status"),
                raw={"stdout": stdout, "stderr": stderr},
                notes=notes,
            )

        except subprocess.TimeoutExpired:
            return SteghideResult(
                tool="steghide",
                ok=False,
                action="info",
                file=file_path,
                cmd=cmd,
                info={},
                extracted=[],
                errors="Timeout while running steghide info.",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )
        except Exception as e:
            return SteghideResult(
                tool="steghide",
                ok=False,
                action="info",
                file=file_path,
                cmd=cmd,
                info={},
                extracted=[],
                errors=f"Error running steghide info: {e}",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

    def _run_extract(self, params: dict) -> SteghideResult:
        file_path = (params or {}).get("file_path") or ""
        notes: List[str] = []

        if not file_path or not os.path.isfile(file_path):
            return SteghideResult(
                tool="steghide",
                ok=False,
                action="extract",
                file=file_path,
                cmd=[],
                info={},
                extracted=[],
                errors="No file selected or invalid path.",
                raw={"stdout": "", "stderr": ""},
                notes=["Select a valid file first."],
            )

        # Detect runtime
        mode, base_cmd, detect_notes = _detect_runtime()
        notes.extend(detect_notes)
        if not base_cmd:
            return SteghideResult(
                tool="steghide",
                ok=False,
                action="extract",
                file=file_path,
                cmd=[],
                info={},
                extracted=[],
                errors="steghide runtime not found (native or WSL).",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )

        # Ask passphrase (blank allowed)
        pw = _prompt_passphrase(title="Steghide Extract", prompt="Enter passphrase (leave blank for none):")

        # We will force an explicit output file in the same folder,
        # so extraction is deterministic and cross-platform.
        out_dir = os.path.dirname(os.path.abspath(file_path))
        out_name = "steghide_extracted.bin"
        out_path = os.path.join(out_dir, out_name)

        file_arg = _maybe_wsl_path(mode, file_path)
        out_arg = _maybe_wsl_path(mode, out_path)

        cmd = base_cmd + ["extract", "-sf", file_arg, "-xf", out_arg, "-f", "-p", pw]

        try:
            proc = _run(cmd, cwd=os.path.dirname(file_path))
            stdout, stderr = proc.stdout, proc.stderr
            ok = proc.returncode == 0 and os.path.exists(out_path)

            # Detect common issues
            if ("format that is not supported" in stdout) or ("biSize: 124" in stdout + stderr):
                notes.append("BMP V5 detected; convert to BMP3: convert input.bmp bmp3:output_v3.bmp")

            if not ok and ("could not extract any data" in (stdout + stderr).lower() or "wrong pass" in (stdout + stderr).lower()):
                notes.append("Possible wrong/empty passphrase or no embedded payload.")

            extracted = [out_path] if ok else []

            return SteghideResult(
                tool="steghide",
                ok=ok,
                action="extract",
                file=file_path,
                cmd=cmd,
                info={},
                extracted=extracted,
                errors=None if ok else (stderr or "Extraction failed or produced no file"),
                raw={"stdout": stdout, "stderr": stderr},
                notes=notes,
            )

        except subprocess.TimeoutExpired:
            return SteghideResult(
                tool="steghide",
                ok=False,
                action="extract",
                file=file_path,
                cmd=cmd,
                info={},
                extracted=[],
                errors="Timeout while running steghide extract.",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )
        except Exception as e:
            return SteghideResult(
                tool="steghide",
                ok=False,
                action="extract",
                file=file_path,
                cmd=cmd,
                info={},
                extracted=[],
                errors=f"Error running steghide extract: {e}",
                raw={"stdout": "", "stderr": ""},
                notes=notes,
            )



