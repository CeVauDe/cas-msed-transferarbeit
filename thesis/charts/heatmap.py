import plotly.graph_objects as go

from charts.config import RYG_COLORSCALE, THESIS_LAYOUT, save_chart


def create_heatmap(
    z_values: list[list[float]],
    x_labels: list[str],
    y_labels: list[str],
    title: str,
    chart_name: str,
    *,
    z_label: str = "",
    show_values: bool = True,
    show_colorbar: bool = True,
    x_side: str = "bottom",
    x_title: str = "",
    y_title: str = "",
    value_format: str = ".1f",
    cell_text: list[list[str]] | None = None,
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Create a heatmap with a red-yellow-green color scale and save as SVG.

    Args:
        cell_text: Optional 2D list of display strings per cell. If provided,
                   these are shown instead of the formatted z_values.
    """
    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=x_labels,
            y=y_labels,
            colorscale=RYG_COLORSCALE,
            colorbar={"title": z_label} if z_label else None,
            showscale=show_colorbar,
            xgap=2,
            ygap=2,
            zmin=0,
            zmax=1,
        )
    )

    if show_values:
        annotations = []
        for i, row in enumerate(z_values):
            for j, val in enumerate(row):
                if val is None:
                    continue
                display = cell_text[i][j] if cell_text else format(val, value_format)
                annotations.append(
                    {
                        "x": x_labels[j],
                        "y": y_labels[i],
                        "text": display,
                        "showarrow": False,
                        "font": {
                            "color": "black" if 0.3 < val < 0.7 else "white",
                            "size": 12,
                        },
                    }
                )
        fig.update_layout(annotations=annotations)

    fig.update_layout(**THESIS_LAYOUT)
    fig.update_layout(
        title={"text": title, "x": 0.5, "xanchor": "center"} if title else None,
        xaxis={"side": x_side, "title": x_title if x_title else None},
        yaxis={
            "autorange": "reversed",
            "title": {"text": y_title, "standoff": 15} if y_title else None,
            "ticksuffix": "  ",
        },
        margin={"l": 0, "r": 0, "t": 0, "b": 0, "autoexpand": True},
    )

    kwargs: dict = {}
    if width is not None:
        kwargs["width"] = width
    if height is not None:
        kwargs["height"] = height
    save_chart(fig, chart_name, **kwargs)


if __name__ == "__main__":
    # Debug entry point — run: cd thesis && python3 -m charts.heatmap
    sample_z = [
        [0.9, 0.6, 0.3],
        [0.4, 0.8, 0.5],
        [0.1, 0.3, 0.95],
    ]
    sample_x = ["Strategie A", "Strategie B", "Strategie C"]
    sample_y = ["Kriterium 1", "Kriterium 2", "Kriterium 3"]
    create_heatmap(
        z_values=sample_z,
        x_labels=sample_x,
        y_labels=sample_y,
        title="Beispiel Heatmap",
        chart_name="debug-heatmap",
        z_label="Score",
    )
    print("Debug heatmap generated.")
