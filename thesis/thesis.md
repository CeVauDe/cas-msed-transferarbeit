# Thesis (Transferarbeit) written in AsciiDoc

This directory contains all the source files of the thesis written in AsciiDoc using Asciidoctor.

## How to setup Asciidoctor

These installation instructions are based on using the [AsciiDoc extension](https://marketplace.visualstudio.com/items?itemName=asciidoctor.asciidoctor-vscode) for VSCode and use a Docker image to run the actual Asciidoctor toolchain for easy installation and PDF generation.

### Requirements
- A recent version of VSCode
- [AsciiDoc VSCode Extension](https://marketplace.visualstudio.com/items?itemName=asciidoctor.asciidoctor-vscode)
- Docker (Desktop)

### Setup & Usage
1. Install the **AsciiDoc** extension.
2. Open [thesis/main.adoc](thesis/main.adoc).
3. To preview the document, use the "Open Preview to the Side" button in the top right corner.
4. To build the PDF manually, run the provided build script from the repository root:
   ```bash
   ./thesis/build.sh
   ```
5. The resulting [thesis/main.pdf](thesis/main.pdf) will be created.

### Continuous Integration
Any changes pushed to the `main` branch will automatically trigger a build via GitHub Actions, and the PDF will be available as a build artifact.
