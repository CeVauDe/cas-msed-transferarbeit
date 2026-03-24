# Red Teaming Evaluations

This folder contains promptfoo red teaming configurations and result files.

## File Overview

| Pattern | Description |
|---|---|
| `*.yaml` | Promptfoo eval configuration |
| `*.config.yaml` | Provider/model configuration for an eval |
| `*.result.json` | Eval results in promptfoo file format (CLI output) |
| `*.manual.result.json` | Manually reviewed/adjusted version of a result file |

## Running an Eval

```bash
# From poc/redteam/
promptfoo redteam run --config korrektheit_C.yaml
```

Results are written to the local promptfoo database and can be viewed with `promptfoo view`.

## Manually correct scoring in the promptfoo UI

Sometimes the evaluation of the LLM judge is not correct and the score can be manually adjusted in the promptfoo UI using the 👍/👎.

To use the corrected scores in a chart, follow the next steps.

## Exporting Results from the UI

If an eval was run previously and is stored in the promptfoo database, export it via the UI:

1. Open `promptfoo view` and navigate to the eval
2. Go to **TEval Resuls** view → **Download eval data and configs** → **JSON Export** (in the Table Data Exports section)
3. Save the downloaded file as `<name>.export.json` (this is a different format than the CLI result files)

## Converting export.json to result.json

The UI JSON export uses a different schema than the CLI result files. The chart generation scripts expect the CLI format. Convert with:

```bash
jq '{results: {results: [.body[] | .outputs[0]]}}' \
  <name>.export.json > <name>.result.json
```

## Generating Charts

Charts are generated from the `thesis/` directory:

```bash
# From repo root
cd thesis
uv run generate_charts.py "korrektheit/pass-rate"   # single chart
uv run generate_charts.py                            # all charts
```

The chart scripts read the `*.result.json` files in this folder. See [generate_charts.py](../thesis/generate_charts.py) for which result files each chart uses.
