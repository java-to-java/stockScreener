"""Orchestrate the full pipeline: constituents -> earnings calendar -> prices
-> knowledge base -> predictions -> dashboard.

    python -m src.pipeline               # run every stage
    python -m src.pipeline --steps constituents,prices,earnings
    python -m src.pipeline --steps kb,predict,dashboard

Each stage is also runnable standalone (``python -m src.fetch_price_history``,
etc.) - this is just a convenience wrapper that runs them in dependency
order and stops on the first hard failure.
"""
import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

STAGES = ["constituents", "earnings", "prices", "kb", "predict", "dashboard"]


def run_stage(stage: str) -> int:
    if stage == "constituents":
        from src.fetch_constituents import main as fn
    elif stage == "earnings":
        from src.fetch_earnings_calendar import main as fn
    elif stage == "prices":
        from src.fetch_price_history import main as fn
    elif stage == "kb":
        from src.knowledge_base import main as fn
    elif stage == "predict":
        from src.predict import main as fn
    elif stage == "dashboard":
        from src.dashboard import main as fn
    else:
        raise ValueError(f"Unknown stage: {stage}")
    log.info("=== Stage: %s ===", stage)
    return fn()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--steps",
        default=",".join(STAGES),
        help=f"Comma-separated stages to run, in order. Choices: {', '.join(STAGES)}",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Keep running later stages even if one fails (useful when NSE "
        "partially rate-limits a run).",
    )
    args = parser.parse_args()

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    unknown = set(steps) - set(STAGES)
    if unknown:
        parser.error(f"Unknown stage(s): {', '.join(sorted(unknown))}")

    failures = []
    for stage in steps:
        code = run_stage(stage)
        if code != 0:
            failures.append(stage)
            log.error("Stage %s failed (exit %d).", stage, code)
            if not args.continue_on_error:
                break

    if failures:
        log.error("Pipeline finished with failures: %s", ", ".join(failures))
        return 1
    log.info("Pipeline finished successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
