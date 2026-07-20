import { Link } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { StatusIndicator } from "../../components/feedback/StatusIndicator";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { PageHeader } from "../../components/ui/PageHeader";

export function AdminOverviewPage() {
  return (
    <section className="stack">
      <PageHeader
        title="Admin"
        description="Operator-facing shell for health, readiness, metrics, and evaluation views."
        actions={
          <Button as={Link} to={routes.adminSystem} variant="secondary">
            System status
          </Button>
        }
      />
      <div className="dashboard-grid">
        <Card>
          <h2>Health</h2>
          <StatusIndicator tone="neutral">Not requested</StatusIndicator>
        </Card>
        <Card>
          <h2>Readiness</h2>
          <StatusIndicator tone="neutral">Not requested</StatusIndicator>
        </Card>
        <Card>
          <h2>Evaluation</h2>
          <StatusIndicator tone="neutral">Not loaded</StatusIndicator>
        </Card>
      </div>
    </section>
  );
}
