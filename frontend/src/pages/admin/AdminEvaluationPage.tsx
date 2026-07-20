import { EmptyState } from "../../components/feedback/EmptyState";
import { PageHeader } from "../../components/ui/PageHeader";

export function AdminEvaluationPage() {
  return (
    <section>
      <PageHeader
        title="Evaluation"
        description="This route is reserved for deterministic evaluation summaries and regression-gate status."
      />
      <EmptyState
        title="No evaluation report loaded"
        message="Evaluation data remains backend-owned until the admin API integration milestone."
      />
    </section>
  );
}
