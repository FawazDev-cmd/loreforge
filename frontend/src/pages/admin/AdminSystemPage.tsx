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
            detail={health ? `Service ${health.service} reports ${health.status}.` : "Not exposed by backend"}
            status={health?.status === "healthy" ? "healthy" : "unavailable"}
            title="API health"
          />
          <OperationalStatusCard
            detail={readiness ? `Service ${readiness.service} reports ${readiness.status}.` : "Not exposed by backend"}
            status={readiness?.status === "ready" ? "healthy" : readiness ? "warning" : "unavailable"}
            title="Readiness"
          />
          <OperationalStatusCard detail="Not exposed by backend" status="unknown" title="Application version" />
          <OperationalStatusCard detail="Not exposed by backend" status="unknown" title="Configured provider" />
          <OperationalStatusCard detail="Represented by /ready only; granular database readiness is not exposed." status="unknown" title="Database readiness" />
          <OperationalStatusCard detail="Not exposed by backend" status="unknown" title="Retrieval readiness" />
        </div>
      ) : null}
    </section>
  );
}