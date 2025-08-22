import { Router } from 'express';
import { listFeatures } from '../pythonBridge.js';

const router = Router();

router.get('/features', async (_req, res) => {
  try {
    const data = await listFeatures();
    if (data.ok === false) return res.status(500).json(data);
    return res.json(data);
  } catch (e: any) {
    return res.status(500).json({ ok: false, error: e?.message || String(e) });
  }
});

export default router;
