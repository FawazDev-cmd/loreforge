"""Command-line entry point for deterministic evaluation regression gates."""

from argparse import ArgumentParser
from pathlib import Path
from sys import stderr, stdout

from loreforge.evaluation.dataset import load_dataset
from loreforge.evaluation.gate import load_thresholds
from loreforge.evaluation.reporting import human_report
from loreforge.evaluation.runner import run_fixture_evaluation

EXIT_SUCCESS = 0
EXIT_REGRESSION = 1
EXIT_CONFIGURATION_ERROR = 2


def main(argv: list[str] | None = None) -> int:
    """Run the deterministic evaluation CLI."""
    parser = ArgumentParser(prog="python -m loreforge.evaluation")
    parser.add_argument(
        "--dataset", required=True, help="Path to evaluation dataset JSON"
    )
    parser.add_argument("--thresholds", required=True, help="Path to threshold JSON")
    parser.add_argument(
        "--output", required=True, help="Path for machine-readable JSON report"
    )
    parser.add_argument(
        "--human", action="store_true", help="Print human-readable report"
    )
    args = parser.parse_args(argv)

    try:
        dataset = load_dataset(Path(args.dataset))
        thresholds = load_thresholds(Path(args.thresholds))
        report = run_fixture_evaluation(dataset=dataset, thresholds=thresholds)
        report.write_json(Path(args.output))
    except Exception as exc:
        stderr.write(f"evaluation configuration error: {type(exc).__name__}\n")
        return EXIT_CONFIGURATION_ERROR

    if args.human:
        stdout.write(human_report(report))
    if report.passed:
        return EXIT_SUCCESS
    return EXIT_REGRESSION
