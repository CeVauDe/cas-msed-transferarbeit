# Chart Generation

Plotly-based chart generation for the thesis. Charts are exported as SVG into `thesis/generated/` and referenced from AsciiDoc.

Dependencies (`plotly`, `kaleido`) are declared as [inline script metadata (PEP 723)](https://packaging.python.org/en/latest/specifications/inline-script-metadata/) in `generate_charts.py` — no separate requirements file needed. `uv run` handles installation automatically.

## Structure

```
thesis/
├── generate_charts.py          # Orchestrator — registers and runs all charts
└── charts/
    ├── __init__.py              # Re-exports chart functions
    ├── config.py                # Shared theme, colors, save_chart() helper
    ├── bar_chart.py             # Vertical bar chart
    └── heatmap.py               # Heatmap (red-yellow-green color scale)
```

## Usage

All commands are run from the repository root.

### Generate all charts

```bash
uv run thesis/generate_charts.py
```

### Generate a single chart by name

```bash
uv run thesis/generate_charts.py sample-bar
uv run thesis/generate_charts.py sample-heatmap
```

### Debug a chart type with sample data

Each chart module has a `__main__` block that renders a sample chart for quick visual verification:

```bash
cd thesis
uv run --with "plotly>=6.0" --with "kaleido>=0.4" -m charts.bar_chart
uv run --with "plotly>=6.0" --with "kaleido>=0.4" -m charts.heatmap
```

Output lands in `thesis/generated/debug-*.svg`.

## Adding a new chart

1. In `generate_charts.py`, add a new function decorated with `@chart("my-chart-name")`:

   ```python
   @chart("my-chart-name")
   def _my_chart():
       create_bar_chart(
           data={"A": 10, "B": 20},
           title="My Chart",
           chart_name="my-chart-name",
       )
   ```

2. Reference it in AsciiDoc:

   ```adoc
   image::generated/my-chart-name.svg[]
   ```

## Adding a new chart type

1. Create a new module in `thesis/charts/` (e.g. `line_chart.py`) following the pattern in `bar_chart.py`.
2. Implement a main function that takes data, title, `chart_name`, and optional layout params, then calls `save_chart()` from `config.py`.
3. Add a `if __name__ == "__main__":` block with sample data for debugging.
4. Export it from `__init__.py`.
