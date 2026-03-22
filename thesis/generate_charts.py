# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "plotly>=6.0",
#     "kaleido>=0.4",
# ]
# ///
"""Generate all thesis charts.

Usage:
    uv run generate_charts.py              # generate all charts
    uv run generate_charts.py CHART_NAME   # generate only the named chart
"""

import sys
from pathlib import Path

# Ensure the thesis directory is on sys.path so `charts` package is importable
# regardless of the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from charts.bar_chart import create_bar_chart
from charts.heatmap import create_heatmap

# ---------------------------------------------------------------------------
# Chart definitions — add new charts here
# ---------------------------------------------------------------------------

CHARTS: dict[str, callable] = {}


def chart(name: str):
    """Decorator to register a chart generator function."""

    def decorator(func):
        CHARTS[name] = func
        return func

    return decorator


# -- Example charts (replace with real thesis data) -------------------------


@chart("sample-bar")
def _sample_bar():
    create_bar_chart(
        data={
            "Q1": 150,
            "Q2": 100,
            "Q3": 170,
            "Q4": 130,
        },
        title="Sample Bar Chart",
        chart_name="sample-bar",
        y_label="Wert",
    )


@chart("sample-heatmap")
def _sample_heatmap():
    create_heatmap(
        z_values=[
            [0.9, 0.6, 0.3],
            [0.4, 0.8, 0.5],
            [0.1, 0.3, 0.95],
        ],
        x_labels=["Strategie A", "Strategie B", "Strategie C"],
        y_labels=["Kriterium 1", "Kriterium 2", "Kriterium 3"],
        title="Sample Heatmap",
        chart_name="sample-heatmap",
        z_label="Score",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else None

    if target:
        if target not in CHARTS:
            print(f"Unknown chart: {target}")
            print(f"Available charts: {', '.join(sorted(CHARTS))}")
            sys.exit(1)
        print(f"Generating chart: {target}")
        CHARTS[target]()
    else:
        print(f"Generating {len(CHARTS)} chart(s)...")
        for name, func in CHARTS.items():
            func()
        print("Done.")


if __name__ == "__main__":
    main()
