import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import pino from 'pino';
import { config } from './config.js';
import runRoute from './routes/run.js';
import featuresRoute from './routes/features.js';
import { notFound, onError } from './middleware/error.js';

const log = pino({ name: 'bs2-node-wrapper' });
const app = express();

app.use(helmet());
app.use(cors({ origin: config.allowOrigin }));
app.use(express.json({ limit: '10mb' }));

app.get('/health', (_req, res) => res.json({ ok: true }));

app.use(featuresRoute);
app.use(runRoute);

app.use(notFound);
app.use(onError);

app.listen(config.port, () => {
  log.info({ port: config.port }, 'Node wrapper listening');
});
