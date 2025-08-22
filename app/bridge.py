# app/bridge.py
from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import sys
from typing import Any, Dict, List, Tuple


# -----------------------------------------------------------------------------
# Make repo root importable even if invoked as "python app/bridge.py"
# -----------------------------------------------------------------------------
HERE = os.path.abspath(os.path.dirname(__file__))      # .../BS-2/app
ROOT = os.path.abspath(os.path.join(HERE, ".."))       # .../BS-2
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------
@contextlib.contextmanager
def _capture_io():
    """Capture stdout/stderr to keep JSON output clean, but return them for diagnostics."""
    old_out, old_err = sys.stdout, sys.stderr
    buf_out, buf_err = io.StringIO(), io.StringIO()
    try:
        sys.stdout, sys.stderr = buf_out, buf_err
        yield buf_out, buf_err
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def _safe_json(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)


# -----------------------------------------------------------------------------
# Manager construction (FeatureManager w/ defaults + definitions preferred)
# -----------------------------------------------------------------------------
def _build_feature_manager() -> Tuple[Any, str]:
    """
    Preferred path: app.core.feature_manager.FeatureManager(DEFAULTS, FEATURE_DEFINITIONS)
    Fallback:       app.core.API.API()
    Returns: (manager_instance, "feature_manager" | "api")
    """
    # Preferred: explicit defaults/definitions just like main.py
    try:
        FeatureManager = importlib.import_module("app.core.feature_manager").FeatureManager
        DEFAULTS = importlib.import_module("app.core.defaults").DEFAULTS
        FEATURE_DEFINITIONS = importlib.import_module("app.core.feature_definitions").FEATURE_DEFINITIONS
        try:
            fm = FeatureManager(defaults=DEFAULTS, feature_definitions=FEATURE_DEFINITIONS, debug=False)
        except TypeError:
            fm = FeatureManager(DEFAULTS, FEATURE_DEFINITIONS)
        # Ensure features are actually loaded
        if hasattr(fm, "scan_features"):
            fm.scan_features()
        if hasattr(fm, "load_features"):
            fm.load_features()
        return fm, "feature_manager"
    except Exception:
        pass

    # Fallback: some repos expose a simpler API manager
    try:
        API = importlib.import_module("app.core.API").API
        try:
            fm = API(debug=False)
        except TypeError:
            fm = API()
        # Try to nudge it to load features
        if hasattr(fm, "scan_features"):
            fm.scan_features()
        if hasattr(fm, "load_features"):
            fm.load_features()
        return fm, "api"
    except Exception as e:
        raise RuntimeError(
            "Unable to construct a manager. Ensure app/core/defaults.py and "
            "app/core/feature_definitions.py exist (with DEFAULTS/FEATURE_DEFINITIONS), "
            "or that app/core/API.py is present."
        ) from e


# -----------------------------------------------------------------------------
# Feature discovery & option invocation
# -----------------------------------------------------------------------------
def _discover_feature_bag(fm: Any) -> Dict[str, Any]:
    for attr in ("features", "_features", "loaded_features"):
        if hasattr(fm, attr):
            bag = getattr(fm, attr)
            if isinstance(bag, dict):
                return bag
    return {}


def list_features_payload(fm: Any) -> Dict[str, Any]:
    bag = _discover_feature_bag(fm)
    items: List[Dict[str, Any]] = []

    for name, rec in bag.items():
        # rec is usually a dict: {instance, easy_options, display_name, description, ...}
        display = name
        desc = ""

        if isinstance(rec, dict):
            display = rec.get("display_name", display)
            desc = rec.get("description", desc)
            ez = rec.get("easy_options")
        else:
            ez = getattr(rec, "easy_options", None)

        options: List[Dict[str, str]] = []
        if ez is not None:
            # Common shapes:
            if hasattr(ez, "list"):
                try:
                    for o in ez.list():
                        oid = o.get("id") or o.get("key")
                        if not oid:
                            continue
                        options.append({"id": oid, "label": o.get("label") or o.get("name") or oid})
                except Exception:
                    pass
            elif hasattr(ez, "options"):
                try:
                    for o in getattr(ez, "options"):
                        oid = getattr(o, "id", getattr(o, "key", None))
                        if not oid:
                            continue
                        options.append({"id": oid, "label": getattr(o, "label", getattr(o, "name", oid))})
                except Exception:
                    pass
            elif isinstance(ez, dict):
                for oid, cb in ez.items():
                    options.append({"id": str(oid), "label": getattr(cb, "__name__", str(oid))})

        items.append({
            "id": name,
            "label": display,
            "description": desc,
            "options": options
        })

    return {"ok": True, "features": items}


def _call_easy_option(ez: Any, option: str, params: Dict[str, Any]) -> Tuple[Any, str, str]:
    with _capture_io() as (buf_out, buf_err):
        if hasattr(ez, "get_option_callable"):
            cb = ez.get_option_callable(option)
            out = cb(params or {})
        elif hasattr(ez, "call"):
            out = ez.call(option, params or {})
        else:
            cb = None
            if isinstance(ez, dict):
                cb = ez.get(option)
            if cb is None:
                cb = getattr(ez, option, None)
            if cb is None:
                raise KeyError(f"Option '{option}' not found")
            out = cb(params or {})
        return out, buf_out.getvalue(), buf_err.getvalue()


def _normalize_output(out: Any, captured_out: str, captured_err: str) -> Tuple[int, Dict[str, Any]]:
    """
    Normalize feature output into JSON:
      - dict/list          -> returned as {"ok": true, "json": ...} unless it already has ok/shape
      - string starting '{' or '[' -> parse as JSON
      - string starting '<' -> treat as HTML
      - anything else       -> convert to string
    Also attaches any captured stdout/stderr into "_prints".
    """
    payload: Dict[str, Any]

    if isinstance(out, (dict, list)):
        # If caller already returned a top-level envelope, pass it through
        if isinstance(out, dict) and ("ok" in out or "html" in out or "json" in out):
            payload = _safe_json(out)
        else:
            payload = {"ok": True, "json": _safe_json(out)}
    elif isinstance(out, str):
        s = out.strip()
        if s.startswith("{") or s.startswith("["):
            try:
                j = json.loads(s)
                if isinstance(j, dict) and ("ok" in j or "html" in j or "json" in j):
                    payload = j
                else:
                    payload = {"ok": True, "json": j}
            except Exception:
                payload = {"ok": True, "result": out}
        elif s.startswith("<"):
            payload = {"ok": True, "html": out}
        else:
            payload = {"ok": True, "result": out}
    else:
        payload = {"ok": True, "result": _safe_json(out)}

    # Attach prints if present
    if captured_out:
        payload.setdefault("_prints", {})["stdout"] = captured_out
    if captured_err:
        payload.setdefault("_prints", {})["stderr"] = captured_err

    if "ok" not in payload:
        payload["ok"] = True

    return 0, payload


def run_option(fm: Any, feature: str, option: str, params: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    bag = _discover_feature_bag(fm)
    rec = bag.get(feature)
    if rec is None:
        return 1, {"ok": False, "error": f"Unknown feature '{feature}'"}

    ez = rec.get("easy_options") if isinstance(rec, dict) else getattr(rec, "easy_options", None)

    # If no EasyOptions, optionally fall back to run_default
    if ez is None:
        inst = rec.get("instance") if isinstance(rec, dict) else getattr(rec, "instance", None)
        if inst is not None and hasattr(inst, "run_default"):
            # If caller asked for "default"/"run_default"/empty, treat as run_default
            if option in (None, "", "default", "run_default", "run"):
                with _capture_io() as (buf_out, buf_err):
                    out = inst.run_default(params or {})
                return _normalize_output(out, buf_out.getvalue(), buf_err.getvalue())
        return 1, {"ok": False, "error": f"Feature '{feature}' has no easy options"}

    try:
        out, pout, perr = _call_easy_option(ez, option, params or {})
        return _normalize_output(out, pout, perr)
    except KeyError as ke:
        return 1, {"ok": False, "error": str(ke)}
    except Exception as e:
        return 1, {"ok": False, "error": f"Option raised: {e.__class__.__name__}: {e}"}


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def _load_params_from_cli(params_str: str, params_file: str | None) -> Dict[str, Any]:
    if params_file:
        with open(params_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("--params-file must contain a JSON object")
        return data

    try:
        data = json.loads(params_str or "{}")
    except Exception as e:
        raise ValueError(f"Invalid --params: {e}")
    if not isinstance(data, dict):
        raise ValueError("--params must be a JSON object")
    return data


def main() -> int:
    p = argparse.ArgumentParser(
        prog="app.bridge",
        description="BS-2 Python bridge for Node wrapper / external callers"
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="List features/options as JSON")
    g.add_argument("--run", action="store_true", help="Run a feature option")

    p.add_argument("--feature", type=str, help="Feature id")
    p.add_argument("--option", type=str, help="Easy option id")
    p.add_argument("--params", type=str, default="{}", help="JSON object as string")
    p.add_argument("--params-file", type=str, default=None, help="Path to a JSON file with params")

    args = p.parse_args()

    # Build manager
    with _capture_io():
        fm, kind = _build_feature_manager()

    if args.list:
        with _capture_io():
            payload = list_features_payload(fm)
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    # --run path
    try:
        params = _load_params_from_cli(args.params, args.params_file)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 2

    code, payload = run_option(fm, args.feature or "", args.option or "", params)
    # You can include manager kind for debugging if you want:
    payload.setdefault("_meta", {})["manager_kind"] = kind
    print(json.dumps(_safe_json(payload), ensure_ascii=False))
    return int(code)


if __name__ == "__main__":
    sys.exit(main())
