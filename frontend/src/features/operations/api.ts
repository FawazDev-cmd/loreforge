import type { ApiClient } from "../../api/client";
import type { HealthResponse, ReadyResponse } from "../../api/contracts";

export type MetricLabels = Record<string, string>;

export type CounterMetric = {
  labels: MetricLabels;
  name: string;
  value: number;
};

export type DurationMetric = {
  count: number;
  labels: MetricLabels;
  max_ms: number;
  name: string;
  total_ms: number;
};

export type MetricsResponse = {
  metrics: {
    counters: CounterMetric[];
    durations: DurationMetric[];
  };
  query_trace_count: number;
  status: "ok" | "unavailable";
};

export type SystemStatusResponse = {
  health: HealthResponse | null;
  healthAvailable: boolean;
  readiness: ReadyResponse | null;
  readinessAvailable: boolean;
};

export function getHealth(apiClient: ApiClient): Promise<HealthResponse> {
  return apiClient.request<HealthResponse>("/health");
}

export function getReadiness(apiClient: ApiClient): Promise<ReadyResponse> {
  return apiClient.request<ReadyResponse>("/ready");
}

export function getMetrics(apiClient: ApiClient): Promise<MetricsResponse> {
  return apiClient.request<MetricsResponse>("/metrics");
}

export async function getSystemStatus(apiClient: ApiClient): Promise<SystemStatusResponse> {
  const [healthResult, readinessResult] = await Promise.allSettled([
    getHealth(apiClient),
    getReadiness(apiClient),
  ]);

  return {
    health: healthResult.status === "fulfilled" ? healthResult.value : null,
    healthAvailable: healthResult.status === "fulfilled",
    readiness: readinessResult.status === "fulfilled" ? readinessResult.value : null,
    readinessAvailable: readinessResult.status === "fulfilled",
  };
}