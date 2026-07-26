import { useQuery } from "@tanstack/react-query";

import { useAuth } from "../auth/useAuth";
import { getMetrics, getSystemStatus } from "./api";

export const systemStatusQueryKey = ["operations", "system-status"] as const;
export const metricsQueryKey = ["operations", "metrics"] as const;

export function useSystemStatusQuery() {
  const { apiClient } = useAuth();

  return useQuery({
    queryFn: () => getSystemStatus(apiClient),
    queryKey: systemStatusQueryKey,
    retry: false,
  });
}

export function useMetricsQuery() {
  const { apiClient } = useAuth();

  return useQuery({
    queryFn: () => getMetrics(apiClient),
    queryKey: metricsQueryKey,
    retry: false,
  });
}