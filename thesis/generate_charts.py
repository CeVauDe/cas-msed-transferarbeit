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


@chart("keine-handlungsanweisungen")
def _keine_handlungsanweisungen():
    plugins = ["Policy", "Custom"]
    strategies = [
        "Crescendo",
        "GOAT",
        "Jailbreak:<br>Composite",
        "Jailbreak:<br>Hydra",
        "Jailbreak:<br>Meta",
        "Mischievous<br>User",
    ]
    # rows = strategies, cols = plugins  (pass_count, total)
    raw = {
        ("Policy", "Crescendo"): (0, 2),
        ("Policy", "GOAT"): (0, 2),
        ("Policy", "Jailbreak:<br>Composite"): (3, 6),
        ("Policy", "Jailbreak:<br>Hydra"): (0, 2),
        ("Policy", "Jailbreak:<br>Meta"): (0, 2),
        ("Policy", "Mischievous<br>User"): (1, 2),
        ("Custom", "Crescendo"): (7, 10),
        ("Custom", "GOAT"): (7, 10),
        ("Custom", "Jailbreak:<br>Composite"): (24, 30),
        ("Custom", "Jailbreak:<br>Hydra"): (8, 10),
        ("Custom", "Jailbreak:<br>Meta"): (8, 10),
        ("Custom", "Mischievous<br>User"): (8, 10),
    }

    z_values = []
    cell_text = []
    for plugin in plugins:
        z_row = []
        text_row = []
        for strategy in strategies:
            passed, total = raw[(plugin, strategy)]
            rate = passed / total
            z_row.append(rate)
            text_row.append(f"{rate:.0%}<br>{passed}/{total}")
        z_values.append(z_row)
        cell_text.append(text_row)

    create_heatmap(
        z_values=z_values,
        x_labels=strategies,
        y_labels=plugins,
        title="",
        chart_name="keine-handlungsanweisungen",
        x_title="Strategie",
        y_title="Plugin",
        z_label="Pass Rate",
        cell_text=cell_text,
        show_colorbar=False,
        x_side="top",
        width=700,
        height=200,
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
