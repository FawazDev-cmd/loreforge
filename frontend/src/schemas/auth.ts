import { z } from "zod";

export const loginSchema = z.object({
  label: z.string().trim().min(1, "Enter a workspace label."),
  apiKey: z.string().trim().min(1, "Enter the demo access code."),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
