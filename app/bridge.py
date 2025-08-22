import argparse, json, sys, os
try:
    from app.core.feature_manager import FeatureManager  
except Exception:
    from app.core.API import API as FeatureManager  

def load_manager():
    try:
        fm = FeatureManager(debug=False)  
    except TypeError:
        fm = FeatureManager()
    if hasattr(fm, "load_features"): fm.load_features()
    if hasattr(fm, "scan_features"): fm.scan_features()
    return fm

def list_features_payload(fm):
    items = []
    candidates = []
    for attr in ("features", "_features", "loaded_features"):
        if hasattr(fm, attr):
            candidates = getattr(fm, attr)
            break

    if isinstance(candidates, dict):
        for name, obj in candidates.items():
            ez = obj.get("easy_options") if isinstance(obj, dict) else getattr(obj, "easy_options", None)
            options = []
            if ez is not None:
                if hasattr(ez, "list"):
                    opts = ez.list()
                    for o in opts:
                        options.append({"id": o["id"], "label": o.get("label", o["id"])})
                elif hasattr(ez, "options"):
                    for o in ez.options:
                        options.append({"id": o.id, "label": getattr(o, "label", o.id)})
            items.append({"id": name, "options": options})
    return {"ok": True, "features": items}

def run_option(fm, feature: str, option: str, params: dict):
    rec = None
    for attr in ("features", "_features", "loaded_features"):
        if hasattr(fm, attr):
            bag = getattr(fm, attr)
            if isinstance(bag, dict) and feature in bag:
                rec = bag[feature]
                break

    if rec is None:
        return 1, {"ok": False, "error": f"Unknown feature '{feature}'"}

    #get EasyOptions
    ez = rec.get("easy_options") if isinstance(rec, dict) else getattr(rec, "easy_options", None)
    if ez is None:
        return 1, {"ok": False, "error": f"Feature '{feature}' has no easy options"}

    #call option
    #convention in our repo: options return HTML OR JSON-string (for *_json)
    if hasattr(ez, "call"):
        out = ez.call(option, params or {})
    else:
        #some versions might expose a callable dict
        cb = getattr(ez, option, None) or (ez.get(option) if isinstance(ez, dict) else None)
        if cb is None:
            return 1, {"ok": False, "error": f"Option '{option}' not found in '{feature}'"}
        out = cb(params or {})

    #if it looks like HTML, wrap; if it looks like JSON, pass through
    try:
        if isinstance(out, str) and out.strip().startswith("{"):
            data = json.loads(out)
            return 0, data
    except Exception:
        pass

    if isinstance(out, str) and out.strip().startswith("<"):
        return 0, {"ok": True, "html": out}

    #already a dict?
    if isinstance(out, (dict, list)):
        return 0, {"ok": True, "json": out}

    #default wrapper
    return 0, {"ok": True, "result": out}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="List features/options as JSON")
    parser.add_argument("--run", action="store_true", help="Run a feature option")
    parser.add_argument("--feature", type=str)
    parser.add_argument("--option", type=str)
    parser.add_argument("--params", type=str, default="{}")
    args = parser.parse_args()

    fm = load_manager()

    if args.list:
        payload = list_features_payload(fm)
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    if args.run:
        try:
            params = json.loads(args.params or "{}")
        except Exception:
            params = {}
        code, payload = run_option(fm, args.feature or "", args.option or "", params)
        print(json.dumps(payload, ensure_ascii=False))
        return code

    print(json.dumps({"ok": False, "error": "No command given (--list/--run)"}))
    return 2

if __name__ == "__main__":
    sys.exit(main())
