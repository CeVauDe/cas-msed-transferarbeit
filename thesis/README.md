# Thesis (Transferarbeit)

AsciiDoc source for the CAS MSED transfer thesis. The document is compiled to PDF using Asciidoctor via Docker.

## Directory Layout

```
thesis/
├── main.adoc                    # Entry point — includes all chapters
├── main.pdf                     # Generated PDF (committed, rebuilt by CI)
├── build.sh                     # Docker-based PDF build script
├── generate_charts.py           # Generates SVG charts from red-team results
├── references.bib               # BibTeX bibliography
├── theme.yml / cover-theme.yml  # PDF theme configuration
├── config/                      # AsciiDoc attributes and settings
├── text/                        # Chapter source files (numbered by order)
│   ├── 01_Zusammenfassung.adoc  # Abstract
│   ├── 10_Einleitung.adoc       # Introduction
│   ├── 20_Methoden.adoc         # Methods (Design Science Research)
│   ├── 30_Ergebnisse_Diskussion/# Results & Discussion (one file per topic)
│   └── 50_Fazit.adoc            # Conclusion
├── charts/                      # Plotly chart modules (see charts/README.md)
└── generated/                   # Output directory for SVG charts
```

## Building the PDF

### Prerequisites

- Docker (Desktop or Engine)
- (Optional) VSCode with the [AsciiDoc extension](https://marketplace.visualstudio.com/items?itemName=asciidoctor.asciidoctor-vscode) for live preview — open `main.adoc` and use "Open Preview to the Side" for a rendered view without building the PDF

### Build

Run from the **repository root**:

```bash
./thesis/build.sh                                          # full build, unchanged
./thesis/build.sh --no-chart-creation                      # skip charts, full post-processing
./thesis/build.sh --no-post-processing                     # generate charts, single-pass PDF
./thesis/build.sh --no-chart-creation --no-post-processing # fastest debug build
```

Output: `thesis/main.pdf`

### Continuous Integration

Every push to `main` triggers `.github/workflows/build-pdf.yml`, which builds the PDF and uploads it as a GitHub Actions artifact.

## Generating Charts

Charts are generated from red-team evaluation results in `poc/redteam/` and exported as SVG into `thesis/generated/`. They are then embedded in the AsciiDoc source.

Run from the **repository root**:

```bash
# Generate all charts
uv run thesis/generate_charts.py

# Generate a single chart by name
uv run thesis/generate_charts.py korrektheit/pass-rate
```

Dependencies (`plotly`, `kaleido`) are declared as [inline script metadata (PEP 723)](https://packaging.python.org/en/latest/specifications/inline-script-metadata/) in `generate_charts.py` — `uv run` installs them automatically, no separate setup needed.

See [charts/README.md](charts/README.md) for details on adding new charts or chart types.
