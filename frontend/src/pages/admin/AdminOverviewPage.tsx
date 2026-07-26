import { Link } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { PageHeader } from "../../components/ui/PageHeader";

export function AdminOverviewPage() {
  return (
    <section className="stack">
      <PageHeader
        title="Engineering Operations"
        description="A safe production-readiness view: health, readiness, metrics, and evaluation posture without unsupported administrator controls."
        actions={
          <Button as={Link} to={routes.adminSystem} variant="secondary">
            System status
          </Button>
        }
      />
      <div className="dashboard-grid">
        <Card className="operation-card">
          <h2>System</h2>
          <p className="muted">Confirm the API is healthy and ready using backend-supported checks.</p>
          <Link to={routes.adminSystem}>Open system view</Link>
        </Card>
        <Card className="operation-card">
          <h2>Metrics</h2>
          <p className="muted">Inspect aggregate counters and duration snapshots without exposing secrets or high-cardinality labels.</p>
          <Link to={routes.adminMetrics}>Open metrics view</Link>
        </Card>
        <Card className="operation-card">
          <h2>Evaluation</h2>
          <p className="muted">See the honest current state: deterministic evaluation exists, but the summary API is not exposed.</p>
          <Link to={routes.adminEvaluation}>Open evaluation view</Link>
        </Card>
      </div>
    </section>
  );
}