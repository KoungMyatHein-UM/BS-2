from typing import Any, Dict

#defaults are applied first; per-feature overrides replace these keys.
DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "cached": False,          #kept for future use if you add caching
    "display_name": "",       #human name in UI/logs
    "version": "v1_0",        #directory name under features/<name>/<version>/
    "description": "",
    "icon": "🧩",
}
