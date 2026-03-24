# cas-msed-transferarbeit

CAS MSED (Modern Software Engineering & Development) transfer thesis by Markus Gruber and Christian Vetter, Lucerne University of Applied Sciences.

The thesis examines whether Large Language Models (LLMs) can reliably answer factual questions about structured data while respecting explicit constraints — specifically: no prognoses, no interpretations beyond the data, and no action recommendations.

The accompanying Proof of Concept (PoC) implements a Gradio chatbot backed by an OpenAI agent that queries Swiss TV audience statistics (Mediapulse annual reports 2018–2021) through constrained MCP (Model Context Protocol) servers. Correctness and constraint adherence were evaluated using promptfoo red-team evaluations.

## Repository Layout

```
cas-msed-transferarbeit/
├── thesis/          # AsciiDoc thesis source, chart generation, generated PDF
├── poc/             # Python implementation: chatbot, MCP servers, red-team evals
└── .github/         # CI/CD: PDF build, PoC lint/test pipeline
```

- [thesis/](thesis/) — AsciiDoc source, build script, chart generation, bibliography
- [poc/](poc/) — Python workspace (uv): chatbot app, MCP server(s), Docker Compose, tests, red-team evals

## Quick Start (PoC)

The only prerequisites are Docker, Docker Compose, and an OpenAI API key:

```bash
cd poc
cp .env.example .env      # add OPENAI_API_KEY
docker compose up --build # builds images, downloads data, starts all services
```

Then open **http://localhost:7860** for the Gradio chat UI.

See [poc/README.md](poc/README.md) for full setup instructions, local development, and architecture details.

## Thesis

The thesis is written in AsciiDoc and compiled to PDF via a Docker-based Asciidoctor build. The generated PDF is committed at [thesis/main.pdf](thesis/main.pdf) and rebuilt automatically by CI on every push to `main`.

See [thesis/README.md](thesis/README.md) for build instructions.

## License

MIT — Copyright 2026 CeVauDe (Markus Gruber, Christian Vetter)
