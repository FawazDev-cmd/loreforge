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
        description="Backend-supported health and readiness checks. Secrets, environment variables, and internal paths are never displayed."
      />
      {systemStatus.isLoading ? <LoadingState label="Loading system status." /> : null}
      {systemStatus.isError ? (
        <ErrorState message="LoreForge could not load system status." title="System status unavailable" />
      ) : null}
      {systemStatus.data ? (
        <div className="dashboard-grid">
          <OperationalStatusCard
            detail={health ? `Service ${health.service} reports ${health.status}.` : "Health endpoint is not available."}
            status={health?.status === "healthy" ? "healthy" : "unavailable"}
            title="API health"
          />
          <OperationalStatusCard
            detail={readiness ? `Service ${readiness.service} reports ${readiness.status}.` : "Readiness endpoint is not available."}
            status={readiness?.status === "ready" ? "healthy" : readiness ? "warning" : "unavailable"}
            title="Readiness"
          />
          <OperationalStatusCard detail="Version is not exposed by the backend API." status="unknown" title="Application version" />
          <OperationalStatusCard detail="Provider details are intentionally not exposed in the UI." status="unknown" title="Configured provider" />
          <OperationalStatusCard detail="Database readiness is represented by lifecycle readiness only." status="unknown" title="Database readiness" />
          <OperationalStatusCard detail="Retrieval readiness is not exposed as a separate backend check." status="unknown" title="Retrieval readiness" />
        </div>
      ) : null}
    </section>
  );
}