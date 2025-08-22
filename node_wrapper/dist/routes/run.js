import { Router } from 'express';
import { RunRequestSchema } from '../types.js';
import { runFeature } from '../pythonBridge.js';
const router = Router();
router.post('/run', async (req, res) => {
    const parsed = RunRequestSchema.safeParse(req.body);
    if (!parsed.success) {
        return res.status(400).json({ ok: false, error: parsed.error.flatten() });
    }
    const { feature, option, params } = parsed.data;
    try {
        const resp = await runFeature(feature, option, params);
        if (resp.ok === false)
            return res.status(500).json(resp);
        return res.json(resp);
    }
    catch (e) {
        return res.status(500).json({ ok: false, error: e?.message || String(e) });
    }
});
export default router;
