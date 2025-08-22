export function notFound(_req, res) {
    res.status(404).json({ ok: false, error: 'Not Found' });
}
export function onError(err, _req, res, _next) {
    res.status(500).json({ ok: false, error: err?.message || String(err) });
}
