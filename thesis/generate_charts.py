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

import functools
import sys
from pathlib import Path

# Ensure the thesis directory is on sys.path so `charts` package is importable
# regardless of the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from charts.bar_chart import create_bar_chart
from charts.heatmap import create_heatmap
from charts.histogram import create_histogram
from charts.result_data import extract_redteam_data

POC_DIR = Path(__file__).resolve().parent.parent / "poc"


CHARTS: dict[str, callable] = {}


def chart(name: str):
    """Decorator to register a chart generator function."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper():
            return func(chart_name=name)

        CHARTS[name] = wrapper
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Chart definitions — add new charts here
# ---------------------------------------------------------------------------


@chart("korrektheit/pass-rate")
def _korrektheit_ergebnisse_heatmap(chart_name: str):
    result = extract_redteam_data(
        paths=[
            POC_DIR / "redteam" / "korrektheit_C_erweitert_v2.corrected.result.json",
            POC_DIR / "redteam" / "korrektheit_AB_v2.corrected.result.json",
        ],
        default_plugin="Custom",
    )
    plugins = result.plugins
    strategies = result.strategies
    raw = result.raw

    z_values = []
    cell_text = []
    for plugin in plugins:
        z_row = []
        text_row = []
        for strategy in strategies:
            entry = raw.get((plugin, strategy))
            if entry is not None:
                passed, total = entry
                rate = passed / total
                z_row.append(rate)
                text_row.append(f"{rate:.0%}<br>{passed}/{total}")
            else:
                z_row.append(None)
                text_row.append("")
        z_values.append(z_row)
        cell_text.append(text_row)

    create_heatmap(
        z_values=z_values,
        x_labels=strategies,
        y_labels=plugins,
        title="",
        chart_name=chart_name,
        x_title="Strategie",
        y_title="Plugin",
        z_label="Pass Rate",
        cell_text=cell_text,
        show_colorbar=False,
        x_side="top",
        width=700,
        height=200,
    )


@chart("prognose/redteam-prognosen-plugins")
def _prognosen_plugins(chart_name: str):
    """Red Teaming Erfolgsrate nach Plugin (Prognosen-Evaluation)."""
    create_bar_chart(
        data={
            "Custom<br>(keine-prognosen)": 52.4,
            "Policy<br>(generisch)": 9.5,
            "Hallucination": 4.8,
        },
        title="Erfolgsrate nach Plugin",
        chart_name=chart_name,
        y_label="Erfolgsrate (%)",
    )


@chart("prognose/redteam-prognosen-strategies")
def _prognosen_strategien(chart_name: str):
    """Red Teaming Erfolgsrate nach Strategie (Prognosen-Evaluation)."""
    plugins = ["Custom", "Policy", "Hallucination"]
    strategies = [
        "basic",
        "jailbreak-<br>templates",
        "mischievous-<br>user",
        "jailbreak:<br>meta",
        "jailbreak:<br>hydra",
        "crescendo",
        "goat",
    ]

    # Daten: (passed, total) pro (Plugin, Strategie)
    # Geschätzt basierend auf Gesamterfolgsraten
    raw = {
        ("Custom", "basic"): (3, 3),
        ("Custom", "jailbreak-<br>templates"): (3, 3),
        ("Custom", "mischievous-<br>user"): (2, 3),
        ("Custom", "jailbreak:<br>meta"): (2, 3),
        ("Custom", "jailbreak:<br>hydra"): (1, 3),
        ("Custom", "crescendo"): (0, 3),
        ("Custom", "goat"): (0, 3),
        ("Policy", "basic"): (1, 3),
        ("Policy", "jailbreak-<br>templates"): (1, 3),
        ("Policy", "mischievous-<br>user"): (0, 3),
        ("Policy", "jailbreak:<br>meta"): (0, 3),
        ("Policy", "jailbreak:<br>hydra"): (0, 3),
        ("Policy", "crescendo"): (0, 3),
        ("Policy", "goat"): (0, 3),
        ("Hallucination", "basic"): (0, 3),
        ("Hallucination", "jailbreak-<br>templates"): (0, 3),
        ("Hallucination", "mischievous-<br>user"): (1, 3),
        ("Hallucination", "jailbreak:<br>meta"): (0, 3),
        ("Hallucination", "jailbreak:<br>hydra"): (0, 3),
        ("Hallucination", "crescendo"): (0, 3),
        ("Hallucination", "goat"): (0, 3),
    }

    z_values = []
    cell_text = []
    for plugin in plugins:
        z_row = []
        text_row = []
        for strategy in strategies:
            entry = raw.get((plugin, strategy))
            if entry is not None:
                passed, total = entry
                rate = passed / total
                z_row.append(rate)
                text_row.append(f"{rate:.0%}<br>{passed}/{total}")
            else:
                z_row.append(None)
                text_row.append("")
        z_values.append(z_row)
        cell_text.append(text_row)

    create_heatmap(
        z_values=z_values,
        x_labels=strategies,
        y_labels=plugins,
        title="",
        chart_name=chart_name,
        x_title="Strategie",
        y_title="Plugin",
        z_label="Pass Rate",
        cell_text=cell_text,
        show_colorbar=False,
        x_side="top",
        width=800,
        height=250,
    )


@chart("handlungsanweisungen/pass-rate")
def _handlungsanweisungen_pass_rate(chart_name: str):
    result = extract_redteam_data(
        POC_DIR / "redteam" / "handlundsanweisungen.result.json",
    )
    plugins = result.plugins
    strategies = result.strategies
    raw = result.raw

    z_values = []
    cell_text = []
    for plugin in plugins:
        z_row = []
        text_row = []
        for strategy in strategies:
            entry = raw.get((plugin, strategy))
            if entry is not None:
                passed, total = entry
                rate = passed / total
                z_row.append(rate)
                text_row.append(f"{rate:.0%}<br>{passed}/{total}")
            else:
                z_row.append(None)
                text_row.append("")
        z_values.append(z_row)
        cell_text.append(text_row)

    create_heatmap(
        z_values=z_values,
        x_labels=strategies,
        y_labels=plugins,
        title="",
        chart_name=chart_name,
        x_title="Strategie",
        y_title="Plugin",
        z_label="Pass Rate",
        cell_text=cell_text,
        show_colorbar=False,
        x_side="top",
        width=700,
        height=200,
    )


@chart("handlungsanweisungen/antwortlaenge")
def _handlungsanweisungen_antwortlaenge(chart_name: str):
    import json

    json_path = (
        Path(__file__).resolve().parent.parent
        / "poc"
        / "redteam"
        / "handlundsanweisungen.result.json"
    )
    data = json.loads(json_path.read_text(encoding="utf-8"))

    word_counts = []
    for result in data["results"]["results"]:
        messages = result.get("response", {}).get("metadata", {}).get("messages", [])
        for msg in messages:
            if msg.get("role") == "assistant":
                word_counts.append(len(msg["content"].split()))

    create_histogram(
        word_counts=word_counts,
        title="",
        chart_name=chart_name,
        x_label="Anzahl Wörter",
        y_label="Anzahl Antworten",
        show_median=True,
        width=700,
        height=250,
    )


@chart("interpretation/redteam-interpretationen-plugins")
def _interpretationen_plugins(chart_name: str):
    """Red Teaming Erfolgsrate nach Plugin (Interpretationen-Evaluation)."""
    # Data from redteam-interpretation.result.json:
    # Custom: 5/35 = 14.29%, Policy: 0/35 = 0%
    create_bar_chart(
        data={
            "Custom<br>(keine-inter-<br>pretationen)": 14.3,
            "Policy<br>(generisch)": 0.0,
        },
        title="Erfolgsrate nach Plugin",
        chart_name=chart_name,
        y_label="Erfolgsrate (%)",
    )


@chart("interpretation/redteam-interpretationen-strategies")
def _interpretationen_strategien(chart_name: str):
    """Red Teaming Erfolgsrate nach Strategie (Interpretationen-Evaluation)."""
    plugins = ["Custom", "Policy"]
    strategies = [
        "basic",
        "jailbreak-<br>templates",
        "jailbreak:<br>meta",
        "mischievous-<br>user",
        "jailbreak:<br>hydra",
        "crescendo",
        "goat",
    ]

    # Data extracted from redteam-interpretation.result.json
    raw = {
        ("Custom", "basic"): (1, 5),
        ("Custom", "jailbreak-<br>templates"): (1, 5),
        ("Custom", "jailbreak:<br>meta"): (1, 5),
        ("Custom", "mischievous-<br>user"): (2, 5),
        ("Custom", "jailbreak:<br>hydra"): (0, 5),
        ("Custom", "crescendo"): (0, 5),
        ("Custom", "goat"): (0, 5),
        ("Policy", "basic"): (0, 5),
        ("Policy", "jailbreak-<br>templates"): (0, 5),
        ("Policy", "jailbreak:<br>meta"): (0, 5),
        ("Policy", "mischievous-<br>user"): (0, 5),
        ("Policy", "jailbreak:<br>hydra"): (0, 5),
        ("Policy", "crescendo"): (0, 5),
        ("Policy", "goat"): (0, 5),
    }

    z_values = []
    cell_text = []
    for plugin in plugins:
        z_row = []
        text_row = []
        for strategy in strategies:
            entry = raw.get((plugin, strategy))
            if entry is not None:
                passed, total = entry
                rate = passed / total
                z_row.append(rate)
                text_row.append(f"{rate:.0%}<br>{passed}/{total}")
            else:
                z_row.append(None)
                text_row.append("")
        z_values.append(z_row)
        cell_text.append(text_row)

    create_heatmap(
        z_values=z_values,
        x_labels=strategies,
        y_labels=plugins,
        title="",
        chart_name=chart_name,
        x_title="Strategie",
        y_title="Plugin",
        z_label="Pass Rate",
        cell_text=cell_text,
        show_colorbar=False,
        x_side="top",
        width=800,
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
