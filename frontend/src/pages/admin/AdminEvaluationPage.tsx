import { EmptyState } from "../../components/feedback/EmptyState";
import { PageHeader } from "../../components/ui/PageHeader";
import { OperationalStatusCard } from "../../features/operations/OperationalStatusCard";

export function AdminEvaluationPage() {
  return (
    <section className="stack">
      <PageHeader
        title="Evaluation"
        description="Deterministic retrieval and grounded-answer evaluation status. LoreForge currently exposes evaluation through offline repository tooling, not an HTTP summary endpoint."
      />
      <OperationalStatusCard detail="No evaluation summary endpoint is exposed by the backend." status="unknown" title="Latest run" />
      <EmptyState
        title="Evaluation runs offline"
        message="Regression gates and quality reports are implemented in the backend repository tooling. The frontend does not fabricate pass/fail results without a supported API."
      />
    </section>
  );
}