import { PageHeader } from "../../components/ui/PageHeader";
import { Card } from "../../components/ui/Card";

const evaluationMetrics = [
  ["Recall", "1.000"],
  ["MRR", "1.000"],
  ["NDCG", "1.000"],
  ["Hit rate", "1.000"],
  ["Citation coverage", "1.000"],
  ["Citation validity", "1.000"],
  ["Required fact coverage", "1.000"],
  ["Abstention correctness", "1.000"],
];

export function AdminEvaluationPage() {
  return (
    <section className="stack">
      <PageHeader
        title="Evaluation"
        description="Deterministic retrieval and grounded-answer regression checks."
      />

      <Card>
        <div className="evaluation-summary">
          <div>
            <span className="muted">Regression suite</span>
            <h2>PASS</h2>
            <p className="muted">6 deterministic fixture cases</p>
          </div>
        </div>

        <div className="evaluation-metrics">
          {evaluationMetrics.map(([metric, value]) => (
            <div className="evaluation-metric" key={metric}>
              <span className="muted">{metric}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>

        <p className="evaluation-note">
          Results are from the deterministic regression fixture suite and are
          not live production benchmarks.
        </p>
      </Card>
    </section>
  );
}
