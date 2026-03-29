"""Generate chat-bubble conversation SVGs with optional matplotlib tables."""

from __future__ import annotations

import io
import re
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pyphen

from .config import DEFAULT_FONT, OUTPUT_DIR, ensure_parent_dir

matplotlib.use("Agg")

# Layout constants
BUBBLE_MAX_WIDTH = 450
BUBBLE_PADDING = 12
BUBBLE_RADIUS = 8
BUBBLE_GAP = 14
LINE_HEIGHT = 12
FONT_SIZE = 9
LABEL_FONT_SIZE = 9
LABEL_GAP = 6
CANVAS_WIDTH = 550
CANVAS_PADDING = 16
ICON_SIZE = 12
ICON_GAP = 4
WRAP_CHARS = 99  # characters per line — tuned to fill ~396px at font-size 9

# Colors
COLOR_RIGHT_BG = "#fde8e0"  # attacker bubble
COLOR_RIGHT_BORDER = "#e8a08a"
COLOR_LEFT_BG = "#e3edf7"  # chatbot bubble
COLOR_LEFT_BORDER = "#9bb8d8"
COLOR_TEXT = "#222222"
COLOR_LABEL = "#555555"

# Font Awesome 6 Free (solid) — official SVG paths
# Source: https://github.com/FortAwesome/Font-Awesome/tree/6.x/svgs/solid
# user-secret: viewBox 0 0 448 512
_ICON_USER_SECRET_PATH = (
    "M224 16c-6.7 0-10.8-2.8-15.5-6.1C201.9 5.4 194 0 176 0c-30.5 0-52"
    " 43.7-66 89.4C62.7 98.1 32 112.2 32 128c0 14.3 25 27.1 64.6 35.9c-.4"
    " 4-.6 8-.6 12.1c0 17 3.3 33.2 9.3 48l-59.9 0C38 224 32 230 32"
    " 237.4c0 1.7 .3 3.4 1 5l38.8 96.9C28.2 371.8 0 423.8 0 482.3C0"
    " 498.7 13.3 512 29.7 512l388.6 0c16.4 0 29.7-13.3 29.7-29.7c0-58.5"
    "-28.2-110.4-71.7-143L415 242.4c.6-1.6 1-3.3 1-5c0-7.4-6-13.4-13.4"
    "-13.4l-59.9 0c6-14.8 9.3-31 9.3-48c0-4.1-.2-8.1-.6-12.1C391 155.1"
    " 416 142.3 416 128c0-15.8-30.7-29.9-78-38.6C324 43.7 302.5 0 272"
    " 0c-18 0-25.9 5.4-32.5 9.9c-4.8 3.3-8.8 6.1-15.5 6.1zm56 208l-12.4"
    " 0c-16.5 0-31.1-10.6-36.3-26.2c-2.3-7-12.2-7-14.5 0c-5.2 15.6-19.9"
    " 26.2-36.3 26.2L168 224c-22.1 0-40-17.9-40-40l0-14.4c28.2 4.1 61"
    " 6.4 96 6.4s67.8-2.3 96-6.4l0 14.4c0 22.1-17.9 40-40 40zm-88 96l16"
    " 32L176 480 128 288l64 32zm128-32L272 480 240 352l16-32 64-32z"
)
_ICON_USER_SECRET_VB = (448, 512)

# robot: viewBox 0 0 640 512
_ICON_ROBOT_PATH = (
    "M320 0c17.7 0 32 14.3 32 32l0 64 120 0c39.8 0 72 32.2 72 72l0 272c0"
    " 39.8-32.2 72-72 72l-304 0c-39.8 0-72-32.2-72-72l0-272c0-39.8 32.2-72"
    " 72-72l120 0 0-64c0-17.7 14.3-32 32-32zM208 384c-8.8 0-16 7.2-16"
    " 16s7.2 16 16 16l32 0c8.8 0 16-7.2 16-16s-7.2-16-16-16l-32 0zm96"
    " 0c-8.8 0-16 7.2-16 16s7.2 16 16 16l32 0c8.8 0 16-7.2 16-16s-7.2-16"
    "-16-16l-32 0zm96 0c-8.8 0-16 7.2-16 16s7.2 16 16 16l32 0c8.8 0"
    " 16-7.2 16-16s-7.2-16-16-16l-32 0zM264 256a40 40 0 1 0 -80 0 40 40 0"
    " 1 0 80 0zm152 40a40 40 0 1 0 0-80 40 40 0 1 0 0 80zM48 224l16 0 0"
    " 192-16 0c-26.5 0-48-21.5-48-48l0-96c0-26.5 21.5-48 48-48zm544 0c26.5"
    " 0 48 21.5 48 48l0 96c0 26.5-21.5 48-48 48l-16 0 0-192 16 0z"
)
_ICON_ROBOT_VB = (640, 512)


def _icon_svg(icon: str, x: float, y: float, size: float, color: str) -> str:
    """Return an SVG <g> element rendering a Font Awesome icon."""
    if icon == "user-secret":
        path_d, (vb_w, vb_h) = _ICON_USER_SECRET_PATH, _ICON_USER_SECRET_VB
    elif icon == "robot":
        path_d, (vb_w, vb_h) = _ICON_ROBOT_PATH, _ICON_ROBOT_VB
    else:
        return ""
    scale = size / vb_h
    w = vb_w * scale
    # Center horizontally on x
    tx = x - w / 2
    return (
        f'<g transform="translate({tx},{y}) scale({scale})">'
        f'<path d="{path_d}" fill="{color}"/>'
        f"</g>"
    )


@dataclass
class TableData:
    """A table to embed inside a chat bubble."""

    headers: list[str]
    rows: list[list[str]]


@dataclass
class ChatMessage:
    """One message in a conversation."""

    role: str  # "user" or "assistant"
    label: str  # e.g. "Angreifer", "Chatbot"
    icon: str = ""  # "user-secret" or "robot"
    paragraphs: list[str | TableData] = field(default_factory=list)


_HYPHENATOR = pyphen.Pyphen(lang="de_CH")


def _wrap_text(text: str, max_chars: int = WRAP_CHARS) -> list[str]:
    """Wrap text with German hyphenation, respecting explicit newlines."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        wrapped = textwrap.wrap(
            paragraph,
            width=max_chars,
            break_on_hyphens=True,
            break_long_words=False,
        )
        # Second pass: try to hyphenate words that push a line over
        result: list[str] = []
        for line in wrapped:
            if len(line) <= max_chars:
                result.append(line)
                continue
            result.append(line)

        # Now re-wrap with hyphenation: build lines word by word
        result = _hyphenate_wrap(paragraph, max_chars)
        lines.extend(result if result else [""])
    return lines or [""]


def _hyphenate_wrap(text: str, max_chars: int) -> list[str]:
    """Wrap text word-by-word, splitting long words at hyphenation points."""
    words = text.split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= max_chars:
            current = candidate
            continue

        # Word doesn't fit — try to hyphenate it
        pairs = list(_HYPHENATOR.iterate(word))
        placed = False
        if pairs:
            # Try each split point (longest prefix first)
            for prefix, suffix in pairs:
                candidate_hyph = f"{current} {prefix}-" if current else f"{prefix}-"
                if len(candidate_hyph) <= max_chars:
                    lines.append(candidate_hyph)
                    current = suffix
                    placed = True
                    break

        if not placed:
            # No hyphenation possible or word is short — break before the word
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)
    return lines


def _escape_xml(text: str) -> str:
    """Escape text for safe XML embedding."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fix_path_d(svg: str) -> str:
    """Ensure all <path> elements have a d attribute (prawn-svg requirement)."""

    def _ensure_d(match: re.Match) -> str:
        tag_body = match.group(1)
        if ' d="' not in tag_body and " d='" not in tag_body:
            return f'<path{tag_body} d="M0,0"/>'
        return match.group(0)

    return re.sub(r"<path([^>]*?)(?<!/)/>", _ensure_d, svg)


def _render_table_svg(table: TableData, max_width: float) -> tuple[str, float, float]:
    """Render a table using matplotlib, return (svg_fragment, width, height)."""
    n_cols = len(table.headers)
    n_rows = len(table.rows)

    fig, ax = plt.subplots(figsize=(max_width / 80, (n_rows + 1) * 0.25))
    ax.axis("off")
    ax.margins(0, 0)

    tbl = ax.table(
        cellText=table.rows,
        colLabels=table.headers,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7)
    tbl.scale(1, 1.1)

    # Style header
    for j in range(n_cols):
        cell = tbl[0, j]
        cell.set_facecolor("#d0d0d0")
        cell.set_text_props(weight="bold", fontfamily=DEFAULT_FONT)
    # Style body
    for i in range(1, n_rows + 1):
        for j in range(n_cols):
            cell = tbl[i, j]
            cell.set_facecolor("white")
            cell.set_text_props(fontfamily=DEFAULT_FONT)

    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", transparent=True)
    plt.close(fig)

    buf.seek(0)
    svg_text = buf.getvalue().decode("utf-8")

    # Register SVG namespace to avoid ns0: prefixes
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    root = ET.fromstring(svg_text)

    # Extract viewBox dimensions
    viewbox = root.get("viewBox", "0 0 100 100")
    parts = viewbox.split()
    vb_w, vb_h = float(parts[2]), float(parts[3])

    # Get width/height from the root element (in points)
    w_attr = root.get("width", "")
    h_attr = root.get("height", "")
    svg_w = float(w_attr.replace("pt", "")) if w_attr else vb_w
    svg_h = float(h_attr.replace("pt", "")) if h_attr else vb_h

    # Scale to fit max_width
    scale = min(max_width / svg_w, 1.0)
    actual_w = svg_w * scale
    actual_h = svg_h * scale

    # Extract inner content, skipping metadata
    inner_parts = []
    for child in root:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "metadata":
            continue
        inner_parts.append(ET.tostring(child, encoding="unicode"))

    inner_svg = "\n".join(inner_parts)
    fragment = f'<g transform="scale({scale})">\n  {inner_svg}\n</g>'

    return fragment, actual_w, actual_h


def _calc_text_block_height(text: str) -> float:
    """Calculate height needed for a wrapped text block."""
    lines = _wrap_text(text)
    return len(lines) * LINE_HEIGHT


def create_chat_svg(
    messages: list[ChatMessage],
    chart_name: str,
) -> Path:
    """Render a chat conversation as an SVG file."""
    path = OUTPUT_DIR / f"{chart_name}.svg"
    ensure_parent_dir(path)

    # First pass: compute table SVGs and total height
    table_renders: dict[tuple[int, int], tuple[str, float, float]] = {}
    y_cursor = CANVAS_PADDING

    bubble_infos = []
    for msg_idx, msg in enumerate(messages):
        is_right = msg.role == "user"
        # Label height
        label_h = LABEL_FONT_SIZE + LABEL_GAP
        y_cursor += label_h

        # Calculate content height
        content_h = 0.0
        for para_idx, para in enumerate(msg.paragraphs):
            if para_idx > 0:
                content_h += 6
            if isinstance(para, TableData):
                frag, tw, th = _render_table_svg(
                    para, BUBBLE_MAX_WIDTH - 2 * BUBBLE_PADDING
                )
                table_renders[(msg_idx, para_idx)] = (frag, tw, th)
                content_h += th
            else:
                content_h += _calc_text_block_height(para)

        bubble_h = content_h + 2 * BUBBLE_PADDING
        bubble_infos.append((is_right, msg.label, msg.icon, msg.paragraphs, bubble_h))

        y_cursor += bubble_h + BUBBLE_GAP

    total_height = y_cursor - BUBBLE_GAP + CANVAS_PADDING

    # Second pass: build SVG
    elements = []
    y = CANVAS_PADDING

    for msg_idx, (is_right, label, icon, paragraphs, bubble_h) in enumerate(
        bubble_infos
    ):
        # Position
        if is_right:
            bx = CANVAS_WIDTH - CANVAS_PADDING - BUBBLE_MAX_WIDTH
        else:
            bx = CANVAS_PADDING

        # Label with icon
        if is_right:
            label_x = bx + BUBBLE_MAX_WIDTH - 5
            anchor = "end"
        else:
            label_x = bx + 5
            anchor = "start"

        label_y = y + LABEL_FONT_SIZE

        # Icon
        if icon:
            if is_right:
                # icon before text (to its left); text is right-anchored
                text_x = label_x
                icon_right_x = (
                    text_x
                    - len(label) * LABEL_FONT_SIZE * 0.55
                    - ICON_GAP
                    - ICON_SIZE / 2
                )
                elements.append(
                    f'<text x="{text_x}" y="{label_y}" '
                    f'font-family="{DEFAULT_FONT}" font-size="{LABEL_FONT_SIZE}" '
                    f'font-weight="bold" fill="{COLOR_LABEL}" text-anchor="{anchor}">'
                    f"{_escape_xml(label)}</text>"
                )
                elements.append(
                    _icon_svg(icon, icon_right_x, y + 1, ICON_SIZE, COLOR_LABEL)
                )
            else:
                # icon before text
                icon_left_x = label_x + ICON_SIZE / 2
                elements.append(
                    _icon_svg(icon, icon_left_x, y + 1, ICON_SIZE, COLOR_LABEL)
                )
                elements.append(
                    f'<text x="{label_x + ICON_SIZE + ICON_GAP}" y="{label_y}" '
                    f'font-family="{DEFAULT_FONT}" font-size="{LABEL_FONT_SIZE}" '
                    f'font-weight="bold" fill="{COLOR_LABEL}" text-anchor="{anchor}">'
                    f"{_escape_xml(label)}</text>"
                )
        else:
            elements.append(
                f'<text x="{label_x}" y="{label_y}" '
                f'font-family="{DEFAULT_FONT}" font-size="{LABEL_FONT_SIZE}" '
                f'font-weight="bold" fill="{COLOR_LABEL}" text-anchor="{anchor}">'
                f"{_escape_xml(label)}</text>"
            )

        y += LABEL_FONT_SIZE + LABEL_GAP

        # Bubble rect
        bg = COLOR_RIGHT_BG if is_right else COLOR_LEFT_BG
        border = COLOR_RIGHT_BORDER if is_right else COLOR_LEFT_BORDER
        elements.append(
            f'<rect x="{bx}" y="{y}" width="{BUBBLE_MAX_WIDTH}" '
            f'height="{bubble_h}" rx="{BUBBLE_RADIUS}" ry="{BUBBLE_RADIUS}" '
            f'fill="{bg}" stroke="{border}" stroke-width="1"/>'
        )

        # Content
        cy = y + BUBBLE_PADDING
        tx = bx + BUBBLE_PADDING

        for para_idx, para in enumerate(paragraphs):
            if para_idx > 0:
                cy += 6

            if isinstance(para, TableData):
                frag, tw, th = table_renders[(msg_idx, para_idx)]
                # Center table in bubble
                table_x = tx + (BUBBLE_MAX_WIDTH - 2 * BUBBLE_PADDING - tw) / 2
                elements.append(f'<g transform="translate({table_x}, {cy})">{frag}</g>')
                cy += th
            else:
                lines = _wrap_text(para)
                for line in lines:
                    cy += LINE_HEIGHT
                    elements.append(
                        f'<text x="{tx}" y="{cy - 2}" '
                        f'font-family="{DEFAULT_FONT}" font-size="{FONT_SIZE}" '
                        f'fill="{COLOR_TEXT}">{_escape_xml(line)}</text>'
                    )

        y += bubble_h + BUBBLE_GAP

    svg_content = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{CANVAS_WIDTH}" height="{total_height}" '
        f'viewBox="0 0 {CANVAS_WIDTH} {total_height}">\n'
        + "\n".join(elements)
        + "\n</svg>"
    )

    # Fix <path> elements without d attribute (prawn-svg requirement)
    svg_content = _fix_path_d(svg_content)

    path.write_text(svg_content, encoding="utf-8")
    print(f"  Generated {path.relative_to(OUTPUT_DIR.parent)}")
    return path
