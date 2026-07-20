import { z } from "zod";

const frontendEnvSchema = z.object({
  apiBaseUrl: z.string().url(),
});

export type FrontendConfig = z.infer<typeof frontendEnvSchema>;

export function loadFrontendConfig(
  env: Record<string, string | undefined> = import.meta.env,
): FrontendConfig {
  return frontendEnvSchema.parse({
    apiBaseUrl: env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000",
  });
}

export const frontendConfig = loadFrontendConfig();
