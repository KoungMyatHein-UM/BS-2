import { spawn } from 'child_process';
export function spawnWithTimeout(cmd, args, opts) {
    return new Promise((resolve) => {
        const child = spawn(cmd, args, {
            cwd: opts.cwd,
            shell: false, //important for Windows path handling
            stdio: ['ignore', 'pipe', 'pipe']
        });
        let out = '';
        let err = '';
        const timer = setTimeout(() => {
            try {
                child.kill('SIGKILL');
            }
            catch { }
        }, opts.timeoutMs);
        child.stdout.on('data', (d) => (out += d.toString()));
        child.stderr.on('data', (d) => (err += d.toString()));
        child.on('close', (code) => {
            clearTimeout(timer);
            resolve({ code, stdout: out, stderr: err });
        });
    });
}
