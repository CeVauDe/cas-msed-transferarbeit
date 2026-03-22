import plotly.graph_objects as go

from charts.config import THESIS_LAYOUT, save_chart


def create_bar_chart(
    data: dict[str, float],
    title: str,
    chart_name: str,
    *,
    x_label: str = "",
    y_label: str = "",
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Create a vertical bar chart and save it as SVG."""
    categories = list(data.keys())
    values = list(data.values())

    fig = go.Figure(
        data=[
            go.Bar(
                x=categories,
                y=values,
                marker_color="#4a90e2",
            )
        ]
    )

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center"),
        xaxis_title=x_label,
        yaxis_title=y_label,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="lightgrey"),
        **THESIS_LAYOUT,
    )

    kwargs: dict = {}
    if width is not None:
        kwargs["width"] = width
    if height is not None:
        kwargs["height"] = height
    save_chart(fig, chart_name, **kwargs)


if __name__ == "__main__":
    # Debug entry point — run: cd thesis && python3 -m charts.bar_chart
    sample_data = {
        "Kategorie A": 42,
        "Kategorie B": 28,
        "Kategorie C": 65,
        "Kategorie D": 51,
    }
    create_bar_chart(
        data=sample_data,
        title="Beispiel Balkendiagramm",
        chart_name="debug-bar-chart",
        y_label="Wert",
    )
    print("Debug bar chart generated.")
