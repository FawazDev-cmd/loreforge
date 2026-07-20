import type { ReactNode } from "react";

import { QueryClientProvider } from "@tanstack/react-query";

import { AuthProvider } from "../../features/auth/AuthProvider";
import { createQueryClient } from "./queryClient";

const queryClient = createQueryClient();

type AppProvidersProps = {
  children: ReactNode;
};

export function AppProviders({ children }: AppProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
