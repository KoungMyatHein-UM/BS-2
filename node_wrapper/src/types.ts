import { z } from 'zod'; //run npm install zod if this is being underlined as an error

export const RunRequestSchema = z.object({
  feature: z.string().min(1),
  option: z.string().min(1),
  params: z.record(z.any()).default({})
});

export type RunRequest = z.infer<typeof RunRequestSchema>;

export type BridgeResponse =
  | { ok: true; html?: string; json?: any }
  | { ok: boolean; error?: string; raw?: string; [k: string]: any };

export type FeatureListResponse = {
  ok: boolean;
  features: Array<{
    id: string;
    label?: string;
    options?: Array<{ id: string; label: string }>;
  }>;
  error?: string;
};
