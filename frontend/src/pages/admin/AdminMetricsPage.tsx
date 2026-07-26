import { ErrorState } from "../../components/feedback/ErrorState";
import { LoadingState } from "../../components/feedback/LoadingState";
import { Card } from "../../components/ui/Card";
import { PageHeader } from "../../components/ui/PageHeader";
import { OperationalStatusCard } from "../../features/operations/OperationalStatusCard";
import { useMetricsQuery } from "../../features/operations/hooks";

export function AdminMetricsPage() {
  const metrics = useMetricsQuery();
  const counters = metrics.data?.metrics.counters ?? [];
  const durations = metrics.data?.metrics.durations ?? [];

  return (
    <section className="stack">
      <PageHeader
        title="Metrics"
        description="Aggregate operational metrics exposed by the authenticated /metrics endpoint. Labels are intentionally low-cardinality."
      />
      {metrics.isLoading ? <LoadingState label="Loading metrics." /> : null}
      {metrics.isError ? <ErrorState message="LoreForge could not load operational metrics." title="Metrics unavailable" /> : null}
      {metrics.data ? (
        <>
          <div className="dashboard-grid">
            <OperationalStatusCard
              detail={metrics.data.status === "ok" ? "Metrics snapshot loaded." : "Metrics recorder unavailable."}
              status={metrics.data.status === "ok" ? "healthy" : "unavailable"}
              title="Metrics endpoint"
            />
            <OperationalStatusCard detail={`${counters.length} counter series exposed.`} status="unknown" title="Counters" />
            <OperationalStatusCard detail={`${durations.length} duration series exposed.`} status="unknown" title="Durations" />
          </div>
          <Card className="operation-card">
            <h2>Request and pipeline counters</h2>
            {counters.length > 0 ? (
              <ul className="metric-list">
                {counters.slice(0, 8).map((counter) => (
                  <li key={`${counter.name}:${JSON.stringify(counter.labels)}`}>
                    <span>{counter.name}</span>
                    <strong>{counter.value}</strong>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No counters are present in the current snapshot.</p>
            )}
          </Card>
          <Card className="operation-card">
            <h2>Duration observations</h2>
            {durations.length > 0 ? (
              <ul className="metric-list">
                {durations.slice(0, 8).map((duration) => (
                  <li key={`${duration.name}:${JSON.stringify(duration.labels)}`}>
                    <span>{duration.name}</span>
                    <strong>{duration.count} observations</strong>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No duration observations are present in the current snapshot.</p>
            )}
          </Card>
          <p className="muted">Query trace count: {metrics.data.query_trace_count}</p>
        </>
      ) : null}
    </section>
  );
}