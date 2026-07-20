import { LoadingState } from "../../components/feedback/LoadingState";
import { Card } from "../../components/ui/Card";
import { PageHeader } from "../../components/ui/PageHeader";

export function AdminSystemPage() {
  return (
    <section className="stack">
      <PageHeader
        title="System"
        description="Health, readiness, and runtime metrics belong here once the authenticated API client is wired."
      />
      <Card>
        <LoadingState message="System checks are not connected during the foundation milestone." />
      </Card>
    </section>
  );
}
