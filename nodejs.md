# BS-2 Node Wrapper (REST API for Big Sister)

A lightweight Node.js REST wrapper for the BS-2 (Big Sister) OSINT toolkit.  
It exposes Python features (ExifTool, Zsteg, Steghide, Binwalk, IRIS, etc.) as simple HTTP endpoints by invoking a Python bridge that communicates with the existing `FeatureManager` / `EasyOptions` system.

This enables any client (web UI, Electron, CLI, other services) to call features over HTTP without requiring Python, Ruby, or CLI details in the frontend.

---

## Motivation

- Maintain Python as the source of truth. All CTF/OSINT logic remains in Python.
- Provide a thin HTTP layer that exposes a stable REST interface to the Python bridge.
- Support portable team setups using relative `.env` files to avoid machine-specific absolute paths.
- Remain client-agnostic: any web UI, CLI, or external tool can consume the same API.

---

## Architecture Overview

```
[client] ─HTTP─> [Node wrapper] ─spawn→ [Python bridge] ─calls→ FeatureManager
                 └→ EasyOptions (feature options)
                 ← JSON/HTML response
```

- Node wrapper (`node_wrapper/`) provides `/health`, `/features`, and `/run` endpoints.
- Python bridge (`app/bridge.py`) loads `FeatureManager` (or `API`) and invokes a feature option by ID, returning JSON/HTML to Node.
- Features (e.g., `steghide`, `zsteg`, `binwalk`) follow the EasyOptions pattern and return normalized dicts or HTML.

---

## Project Layout (wrapper)

```
node_wrapper/
  package.json
  tsconfig.json
  .env.example
  src/
    index.ts
    config.ts
    types.ts
    pythonBridge.ts
    routes/
      run.ts
      features.ts
    middleware/
      error.ts
    utils/
      proc.ts
  README.md
```

The Python side resides in the BS-2 repository root (e.g., `app/`, `features/`, `web/`, `main.py`).  
The bridge file is located at `app/bridge.py` inside the BS-2 repository.

---

## Requirements

- Node.js 18 or newer
- Python 3.9 or newer on PATH (or set `PYTHON` to a venv interpreter)
- BS-2 dependencies as required (ExifTool, Steghide, Binwalk, Zsteg/Ruby, etc.)
- Ruby and zsteg (if using Zsteg on Windows; WSL is supported)

---

## Setup

1. Install Node dependencies in the wrapper folder:
   ```bash
   cd node_wrapper
   npm i
   ```

2. Create `.env` (portable, relative paths recommended):

   ```
   # node_wrapper/.env
   PYTHON=python
   PY_BRIDGE=app/bridge.py     # relative to PY_CWD
   PY_CWD=..                   # node_wrapper is inside BS-2 → parent is repo root
   REQUEST_TIMEOUT_MS=300000
   PORT=3000
   ALLOW_ORIGIN=*
   ```

   For absolute paths, use `.env.example` as a template and set PY_BRIDGE & PY_CWD explicitly.
   If using a virtual environment, set PYTHON to its interpreter (e.g., .\.venv\Scripts\python.exe).

3. Run the wrapper:

   ```bash
   # Development (TypeScript watch)
   npm run dev

   # Production
   npm run build
   npm start
   ```

   You should see: `Node wrapper listening { port: 3000 }`

---

## API Testing

### Health

```bash
curl http://localhost:3000/health
# {"ok":true}
```

### List Features (via Python bridge --list)

```bash
curl http://localhost:3000/features
# {"ok":true,"features":[{"id":"steghide","options":[...]} ...]}
```

### Run a Feature Option

PowerShell (JSON):

```powershell
$body = @{
  feature = "zsteg"
  option  = "scan_json"
  params  = @{ file_path = "C:\path\to\image.png" }
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Uri http://localhost:3000/run -Method Post -ContentType 'application/json' -Body $body
```

curl (Windows):

```bash
curl -X POST http://localhost:3000/run ^
  -H "content-type: application/json" ^
  -d "{\"feature\":\"binwalk\",\"option\":\"scan_json\",\"params\":{\"file_path\":\"C:\\\\path\\\\to\\\\file.bin\"}}"
```

#### Examples

- Binwalk signatures: `feature="binwalk"`, `option="scan_json"`
- Binwalk extract: `feature="binwalk"`, `option="extract_json"`, `params={"file_path":"...", "output_dir":"...","matryoshka":true}`
- Steghide info: `feature="steghide"`, `option="info_json"`, `params={"file_path":"..."}`
- Zsteg extract: `feature="zsteg"`, `option="extract_json"`, `params={"file_path":"...","channel":"b1,r,lsb,xy","output_name":"out.bin"}`

#### Response Forms

- `{ ok: true, json: <normalized_dict> }`
- `{ ok: true, html: "<div>...</div>" }`
- `{ ok: false, error: "..." }`

---

## Python Bridge (`app/bridge.py`)

Purpose: Minimal CLI that the Node wrapper spawns for each request.

### How it works

- Loads FeatureManager (or API) and ensures features are scanned/loaded.
- Exposes two CLI modes:
  - `--list`: prints `{"ok": true, "features": [{id, options:[{id,label}]}...]}`.
  - `--run --feature <id> --option <id> --params <json>`: calls the EasyOption and prints its result as JSON.

### Output Handling

- If an option returns HTML (string starting with `<`), bridge wraps it as `{ "ok": true, "html": "..." }`.
- If an option returns a JSON string (starts with `{`), bridge parses and returns that JSON.
- If an option returns a dict/list, bridge wraps it as `{ "ok": true, "json": ... }`.
- Errors are returned as `{ ok: false, error: "..." }` with a non-zero exit code.

### CLI Usage (debugging without Node)

```bash
# from the BS-2 repo root
python app/bridge.py --list

python app/bridge.py --run --feature zsteg --option scan_json --params "{\"file_path\":\"C:\\path\\to\\img.png\"}"
```

### Feature Discovery

The bridge attempts to read features from attributes such as `features`, `_features`, or `loaded_features`.
Each feature record is expected to contain an EasyOptions object (or similar) that can call an option by ID.

---

## API Endpoints

### GET /health

Basic liveness check.

### GET /features

Returns the Python bridge `--list` payload.

### POST /run

Body:

```json
{
  "feature": "zsteg",
  "option": "scan_json",
  "params": { "file_path": "C:\\path\\image.png" }
}
```

Returns:

```json
{ "ok": true, "json": { "...normalized result..." } }
```
or

```json
{ "ok": true, "html": "<div>...</div>" }
```
or an error payload.

---

## Conventions & Normalized Results

Many features expose `*_json` options that return a normalized dict. Examples:

### Steghide

```json
{
  "tool":"steghide","ok":true,"action":"info","file":"...",
  "cmd":["steghide","info","-v","-sf","...","-p",""],
  "info":{"embedded file":"...","encryption":"..."}, "extracted":[],
  "errors": null, "raw":{"stdout":"...","stderr":""}, "notes":["..."]
}
```

### Zsteg

```json
{ "tool":"zsteg","ok":true,"action":"scan","findings":[{"channel":"b1,r,lsb,xy","desc":"text: 'FLAG{...}'"}], ... }
```

### Binwalk

```json
{ "tool":"binwalk","ok":true,"action":"scan","signatures":[{"offset":"0","hex_offset":"0x0","description":"PNG image"}], ... }
```

HTML options return pre-rendered panels using Jinja2 templates in the Python feature modules.

---

## CORS, Security & Timeouts

- `ALLOW_ORIGIN` controls CORS for browsers. Default is `*` for development; restrict in production.
- `REQUEST_TIMEOUT_MS` terminates long-running subprocesses to prevent hanging requests.
- The wrapper does not execute arbitrary shell from HTTP input; it only forwards whitelisted feature/option IDs to the Python system.

---

## Platform Notes (Windows/WSL/Ruby)

- If zsteg is not on Windows PATH, the feature can run via WSL and convert paths automatically.
- The Python feature modules add hints (e.g., BMP V5 to BMP3 conversion) in their notes field.
- Ensure the `file` utility is available for zsteg on Windows (MSYS2/WSL), or use the WSL zsteg path.

---

## Deployment

```bash
cd node_wrapper
npm run build
npm start      # serves dist/index.js
```

Use a process manager (PM2/systemd) and reverse proxy (nginx/Caddy) as needed.

---

## Troubleshooting

- `PY_BRIDGE` not set / `PY_CWD` missing: Check `.env` values (consider the relative example above).
- `spawn ENOENT`: `PYTHON` not resolvable; set to absolute interpreter or ensure it is on PATH.
- Invalid JSON returned by Python bridge: Prefer `*_json` options, or let HTML be wrapped as `{ok:true, html}`.
- Zsteg errors: Install Ruby gem zsteg or run via WSL; ensure `file` utility is present.
- Steghide BMP V5: Convert using `convert