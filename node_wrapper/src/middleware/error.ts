import type { Request, Response, NextFunction } from 'express';

export function notFound(_req: Request, res: Response) {
  res.status(404).json({ ok: false, error: 'Not Found' });
}

export function onError(err: any, _req: Request, res: Response, _next: NextFunction) {
  res.status(500).json({ ok: false, error: err?.message || String(err) });
}
