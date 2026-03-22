import statistics

import plotly.graph_objects as go

from charts.config import THESIS_LAYOUT, save_chart


def create_histogram(
    word_counts: list[int],
    title: str,
    chart_name: str,
    *,
    bin_size: int = 100,
    x_label: str = "",
    y_label: str = "",
    show_median: bool = False,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Create a histogram of word counts and save it as SVG."""
    fig = go.Figure(
        data=[
            go.Histogram(
                x=word_counts,
                xbins={"size": bin_size},
                marker_color="#4a90e2",
                marker_line={"color": "white", "width": 1},
            )
        ]
    )

    fig.update_layout(**THESIS_LAYOUT)
    fig.update_layout(
        title={"text": title, "x": 0.5, "xanchor": "center"} if title else None,
        xaxis_title=x_label,
        yaxis_title=y_label,
        xaxis={"showgrid": False},
        yaxis={"showgrid": True, "gridcolor": "lightgrey"},
        bargap=0,
        margin={"l": 0, "r": 0, "t": 0, "b": 0, "autoexpand": True},
    )

    if show_median:
        median = statistics.median(word_counts)
        fig.update_layout(
            shapes=[
                {
                    "type": "line",
                    "x0": median,
                    "x1": median,
                    "y0": 0,
                    "y1": 1,
                    "yref": "paper",
                    "line": {"color": "#e05c2a", "width": 2, "dash": "dash"},
                }
            ],
            annotations=[
                {
                    "x": median,
                    "y": 1,
                    "yref": "paper",
                    "text": f"Median: {median:.0f}",
                    "showarrow": False,
                    "xanchor": "left",
                    "yanchor": "top",
                    "xshift": 6,
                    "font": {"color": "#e05c2a", "size": 12},
                }
            ],
        )

    kwargs: dict = {}
    if width is not None:
        kwargs["width"] = width
    if height is not None:
        kwargs["height"] = height
    save_chart(fig, chart_name, **kwargs)


if __name__ == "__main__":
    # Debug entry point — run: cd thesis && python3 -m charts.histogram
    import random

    random.seed(42)
    sample_counts = [random.randint(50, 700) for _ in range(80)]
    create_histogram(
        word_counts=sample_counts,
        title="Beispiel Histogramm",
        chart_name="debug-histogram",
        x_label="Anzahl Wörter",
        y_label="Häufigkeit",
    )
