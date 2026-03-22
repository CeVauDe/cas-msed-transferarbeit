import re
from pathlib import Path

import plotly.graph_objects as go

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "generated"

DEFAULT_FONT = "Arial"
DEFAULT_WIDTH = 700
DEFAULT_HEIGHT = 450

# Red → Yellow → Green continuous colorscale
RYG_COLORSCALE = [
    [0.0, "rgb(215, 48, 39)"],
    [0.25, "rgb(252, 141, 89)"],
    [0.5, "rgb(254, 224, 139)"],
    [0.75, "rgb(166, 217, 106)"],
    [1.0, "rgb(26, 150, 65)"],
]

THESIS_LAYOUT = {
    "font": {"family": DEFAULT_FONT, "size": 14},
    "plot_bgcolor": "white",
    "paper_bgcolor": "white",
}


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def save_chart(
    fig: go.Figure,
    chart_name: str,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> Path:
    ensure_output_dir()
    path = OUTPUT_DIR / f"{chart_name}.svg"
    fig.write_image(str(path), format="svg", width=width, height=height)
    _fix_svg(path)
    print(f"  Generated {path.relative_to(OUTPUT_DIR.parent)}")
    return path


def _fix_svg(path: Path) -> None:
    """Fix Plotly SVG quirks that trip up Asciidoctor's prawn-svg renderer."""
    svg = path.read_text()
    # Plotly emits <path class="..."/> without a d attribute — prawn-svg requires it.
    svg = re.sub(r"<path([^>]*?)(?<!/)/>", _ensure_d_attr, svg)
    path.write_text(svg)


def _ensure_d_attr(match: re.Match) -> str:
    tag_body = match.group(1)
    if ' d="' not in tag_body and " d='" not in tag_body:
        return f'<path{tag_body} d="M0,0"/>'
    return match.group(0)
