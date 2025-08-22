import { z } from 'zod'; //run npm install zod if this is being underlined as an error
export const RunRequestSchema = z.object({
    feature: z.string().min(1),
    option: z.string().min(1),
    params: z.record(z.any()).default({})
});
