import path from 'path';
import { spawnWithTimeout } from './utils/proc.js';
import { config } from './config.js';
import type { BridgeResponse } from './types.js';

function ensureBridgeConfigured() {
  if (!config.pythonBridge) {
    throw new Error('PY_BRIDGE not set. Point it to your BS-2/app/bridge.py');
  }
}

export async function runFeature(feature: string, option: string, params: Record<string, any>): Promise<BridgeResponse> {
  ensureBridgeConfigured();

  const args = [
    config.pythonBridge,
    '--run',
    '--feature', feature,
    '--option', option,
    '--params', JSON.stringify(params ?? {})
  ];

  const { code, stdout, stderr } = await spawnWithTimeout(config.pythonCmd, args, {
    cwd: config.pythonCwd,
    timeoutMs: config.timeoutMs
  });

  if (code !== 0) {
    //bridge returns non-zero -> surface structured error
    return { ok: false, error: stderr || `Python exited with ${code}`, raw: stdout };
  }

  //bridge prints JSON (either normalized dict or {ok,html}) — try to parse
  try {
    const parsed = JSON.parse(stdout);
    return parsed;
  } catch {
    //if HTML was returned directly, wrap it
    if (stdout.trim().startsWith('<')) {
      return { ok: true, html: stdout };
    }
    return { ok: false, error: 'Invalid JSON returned by Python bridge', raw: stdout };
  }
}

export async function listFeatures(): Promise<BridgeResponse> {
  ensureBridgeConfigured();
  const args = [config.pythonBridge, '--list'];
  const { code, stdout, stderr } = await spawnWithTimeout(config.pythonCmd, args, {
    cwd: config.pythonCwd,
    timeoutMs: config.timeoutMs
  });

  if (code !== 0) {
    return { ok: false, error: stderr || `Python exited with ${code}` };
  }

  try {
    return JSON.parse(stdout);
  } catch {
    return { ok: false, error: 'Invalid JSON from --list', raw: stdout };
  }
}
