import 'dotenv/config';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { spawnSync } from 'child_process';

function repoRootFromNodeWrapper(): string {
  //node_wrapper/ is the current project; repo root is its parent
  //__dirname = node_wrapper/dist or node_wrapper/src after TS transpile
  //so go up two levels and normalize
  const here = path.resolve(process.cwd());
  //if the user runs from node_wrapper, parent is the repo root
  return path.resolve(here, '..');
}

function resolveCwd(): string {
  const envCwd = process.env.PY_CWD;
  if (!envCwd || envCwd.trim() === '') {
    return repoRootFromNodeWrapper();
  }
  //if PY_CWD is absolute, use it; otherwise resolve relative to node_wrapper
  return path.isAbsolute(envCwd)
    ? envCwd
    : path.resolve(process.cwd(), envCwd);
}

function resolveBridge(pyCwd: string): string {
  const envBridge = process.env.PY_BRIDGE || 'app/bridge.py';
  return path.isAbsolute(envBridge)
    ? envBridge
    : path.resolve(pyCwd, envBridge);
}

function which(cmd: string): string | null {
  const res = spawnSync(process.platform === 'win32' ? 'where' : 'which', [cmd], { encoding: 'utf8' });
  if (res.status === 0 && res.stdout) {
    const first = res.stdout.split(/\r?\n/).find(Boolean);
    return first || null;
  }
  return null;
}

function resolvePython(): string {
  // 1)honor env if set
  if (process.env.PYTHON && process.env.PYTHON.trim() !== '') {
    return process.env.PYTHON;
  }
  // 2)try Windows launcher
  if (process.platform === 'win32' && which('py')) {
    return 'py'; // wrapper uses 'py' (it will run scripts like `py bridge.py ...`)
  }
  // 3)try common names
  return which('python') || which('python3') || 'python';
}

const pythonCwd = resolveCwd();
const pythonBridge = resolveBridge(pythonCwd);
const pythonCmd = resolvePython();

export const config = {
  pythonCmd,
  pythonBridge,
  pythonCwd,
  timeoutMs: Number(process.env.REQUEST_TIMEOUT_MS || 300000),
  port: Number(process.env.PORT || 3000),
  allowOrigin: process.env.ALLOW_ORIGIN || '*',
};

//helpful warnings (non-fatal)
if (!fs.existsSync(config.pythonCwd)) {
  console.warn(`[config] PY_CWD does not exist: ${config.pythonCwd}`);
}
if (!fs.existsSync(config.pythonBridge)) {
  console.warn(`[config] PY_BRIDGE not found: ${config.pythonBridge}`);
}
