"""Machine-readable and human-readable evaluation reports."""

from dataclasses import dataclass
from json import dumps
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class EvaluationRunReport:
    """Serializable deterministic evaluation run report."""

    dataset_name: str
    schema_version: str
    passed: bool
    aggregates: dict[str, float]
    thresholds: dict[str, float | int]
    failed_thresholds: tuple[str, ...]
    cases: tuple[dict[str, Any], ...]
    tag_summaries: dict[str, dict[str, float]]
    errors: tuple[dict[str, str], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-compatible report data without sensitive raw content."""
        return {
            "dataset_name": self.dataset_name,
            "schema_version": self.schema_version,
            "passed": self.passed,
            "aggregates": self.aggregates,
            "thresholds": self.thresholds,
            "failed_thresholds": list(self.failed_thresholds),
            "cases": list(self.cases),
            "tag_summaries": self.tag_summaries,
            "errors": list(self.errors),
        }

    def to_json(self) -> str:
        """Serialize report as deterministic pretty JSON."""
        return dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"

    def write_json(self, path: Path | str) -> None:
        """Write machine-readable JSON report."""
        Path(path).write_text(self.to_json(), encoding="utf-8")


def human_report(report: EvaluationRunReport) -> str:
    """Render a compact human-readable evaluation report."""
    status = "PASS" if report.passed else "FAIL"
    lines = [
        f"Evaluation: {status}",
        f"Dataset: {report.dataset_name} ({report.schema_version})",
        "Aggregates:",
    ]
    for key, value in sorted(report.aggregates.items()):
        lines.append(f"- {key}: {value:.3f}")
    if report.failed_thresholds:
        lines.append("Failed thresholds:")
        for threshold in report.failed_thresholds:
            lines.append(f"- {threshold}")
    failed_cases = tuple(case for case in report.cases if not case["passed"])
    if failed_cases:
        lines.append("Failed cases:")
        for case in failed_cases:
            reason = "; ".join(case["failure_reasons"])
            lines.append(f"- {case['case_id']}: {reason}")
    if report.errors:
        lines.append("Evaluator errors:")
        for error in report.errors:
            lines.append(f"- {error['case_id']}: {error['category']}")
    return "\n".join(lines) + "\n"
