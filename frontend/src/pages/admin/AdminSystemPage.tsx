import { ErrorState } from "../../components/feedback/ErrorState";
import { LoadingState } from "../../components/feedback/LoadingState";
import { PageHeader } from "../../components/ui/PageHeader";
import { OperationalStatusCard } from "../../features/operations/OperationalStatusCard";
import { useSystemStatusQuery } from "../../features/operations/hooks";

export function AdminSystemPage() {
  const systemStatus = useSystemStatusQuery();
  const health = systemStatus.data?.health;
  const readiness = systemStatus.data?.readiness;

  return (
    <section className="stack">
      <PageHeader
        title="System"
        description="Backend-supported health and readiness checks for the loreForge service."
      />
      {systemStatus.isLoading ? <LoadingState label="Loading system status." /> : null}
      {systemStatus.isError ? (
        <ErrorState message="LoreForge could not load system status." title="System status unavailable" />
      ) : null}
      {systemStatus.data ? (
        <div className="dashboard-grid">
          <OperationalStatusCard
            detail={
              health
                ? `Service ${health.service} reports ${health.status}.`
                : "Health endpoint is not available."
            }
            status={health?.status === "healthy" ? "healthy" : "unavailable"}
            title="API health"
          />

          <OperationalStatusCard
            detail={readinessDetail(readiness)}
            status={readinessStatus(readiness)}
            title="Readiness"
          />
        </div>

      ) : null}
    </section>
  );
}

function readinessDetail(readiness: { ready: boolean } | null | undefined): string {
  if (!readiness) {
    return "Readiness status could not be retrieved.";
  }
  return readiness.ready
    ? "Application startup and warm-up completed successfully."
    : "Application startup or warm-up has not completed.";
}

function readinessStatus(readiness: { ready: boolean } | null | undefined) {
  if (!readiness) {
    return "unknown";
  }
  return readiness.ready ? "healthy" : "warning";
}
