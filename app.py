import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html

import data_fetch as fetch

DAY_ORDER = fetch.DAY_ORDER

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#495057", size=12),
    margin=dict(l=48, r=24, t=56, b=48),
    title=dict(font=dict(size=15, color="#003262")),
    xaxis=dict(gridcolor="#e9ecef", linecolor="#dee2e6"),
    yaxis=dict(gridcolor="#e9ecef", linecolor="#dee2e6"),
)

COLOR_SCALE = "RdYlGn_r"


def format_hour(hour: int) -> str:
    return fetch.format_hour_label(hour)


def apply_chart_style(fig, height=380):
    fig.update_layout(**CHART_LAYOUT, height=height)
    return fig


def compute_insights(df: pd.DataFrame) -> dict:
    avg_capacity = float(df["percentage_capacity"].mean())
    weekday_avgs = (
        df.groupby("weekday")["percentage_capacity"].mean().reindex(DAY_ORDER).dropna()
    )
    hourly_avgs = df.groupby("hour")["percentage_capacity"].mean().sort_values()
    peak_hours_avg = float(
        df[df["hour"].isin([16, 17, 18])]["percentage_capacity"].mean()
    )

    return {
        "avg_capacity": avg_capacity,
        "least_busy_day": weekday_avgs.idxmin(),
        "least_busy_day_avg": float(weekday_avgs.min()),
        "most_busy_day": weekday_avgs.idxmax(),
        "most_busy_day_avg": float(weekday_avgs.max()),
        "least_busy_hour": int(hourly_avgs.idxmin()),
        "least_busy_hour_avg": float(hourly_avgs.min()),
        "peak_hours_avg": peak_hours_avg,
        "date_start": df["pst_timestamp"].min().strftime("%b %d, %Y"),
        "date_end": df["pst_timestamp"].max().strftime("%b %d, %Y"),
        "total_readings": len(df),
    }


def create_heatmap(pivot: pd.DataFrame):
    ordered_pivot = pivot.reindex(DAY_ORDER)
    fig = px.imshow(
        ordered_pivot,
        labels=dict(x="Hour", y="Day", color="Occupancy %"),
        color_continuous_scale=COLOR_SCALE,
        aspect="auto",
    )
    fig.update_layout(
        title="Average Occupancy by Day & Hour",
        xaxis_title="Hour of Day",
        yaxis_title="",
    )
    return apply_chart_style(fig, height=420)


def create_daily_average(df: pd.DataFrame, avg_capacity: float):
    daily_avg = (
        df.groupby("weekday")["percentage_capacity"]
        .mean()
        .reindex(DAY_ORDER)
        .reset_index()
    )
    fig = px.bar(
        daily_avg,
        x="weekday",
        y="percentage_capacity",
        labels={"percentage_capacity": "Avg. Occupancy %", "weekday": "Day"},
        color="percentage_capacity",
        color_continuous_scale=COLOR_SCALE,
    )
    fig.update_layout(title="Average Occupancy by Day of Week")
    fig.add_hline(
        y=avg_capacity,
        line_dash="dash",
        line_color="#003262",
        annotation_text=f"Overall avg: {avg_capacity:.1f}%",
        annotation_font_color="#003262",
    )
    return apply_chart_style(fig)


def create_hourly_average(df: pd.DataFrame):
    hourly_avg = df.groupby("hour")["percentage_capacity"].mean().reset_index()
    hourly_avg["hour_label"] = hourly_avg["hour"].apply(format_hour)
    fig = px.line(
        hourly_avg,
        x="hour",
        y="percentage_capacity",
        labels={"percentage_capacity": "Avg. Occupancy %", "hour": "Hour"},
        markers=True,
        color_discrete_sequence=["#003262"],
    )
    fig.update_layout(
        title="Average Occupancy by Hour of Day",
        xaxis=dict(
            tickmode="array",
            tickvals=hourly_avg["hour"],
            ticktext=hourly_avg["hour_label"],
        ),
    )
    return apply_chart_style(fig)


def create_histogram(df: pd.DataFrame):
    fig = px.histogram(
        df,
        x="percentage_capacity",
        nbins=30,
        color_discrete_sequence=["#004d7a"],
    )
    fig.update_layout(
        title="Distribution of Occupancy Readings",
        xaxis_title="Occupancy %",
        yaxis_title="Number of Readings",
    )
    return apply_chart_style(fig)


def kpi_card(label, value, subtitle):
    return dbc.Card(
        dbc.CardBody(
            [
                html.P(label, className="kpi-label mb-1"),
                html.P(value, className="kpi-value mb-1"),
                html.P(subtitle, className="text-muted mb-0", style={"fontSize": "0.8rem"}),
            ]
        ),
        className="kpi-card",
    )


def insight_block(label, value, detail):
    return html.Div(
        [
            html.P(label, className="insight-label"),
            html.P(value, className="insight-value"),
            html.P(detail, className="text-muted mb-0", style={"fontSize": "0.85rem"}),
        ],
        className="insight-item",
    )


def navbar():
    return dbc.Navbar(
        dbc.Container(
            [
                html.Div(
                    [
                        html.Span(
                            "RSF Occupancy Tracker",
                            className="navbar-brand fw-bold text-white",
                        ),
                        html.Span(
                            " UC Berkeley Recreational Sports Facility",
                            className="navbar-brand-subtitle d-none d-md-inline",
                        ),
                    ]
                ),
            ],
            fluid=True,
        ),
        color="dark",
        dark=True,
        className="mb-4 py-3",
        style={"backgroundColor": "#003262"},
    )


def build_unavailable_layout(error_message: str):
    return dbc.Container(
        [
            navbar(),
            html.Div(
                [
                    html.H1("Occupancy data unavailable"),
                    html.P(
                        "The dashboard could not load gym occupancy readings. "
                        "Check Google Sheets access and try again."
                    ),
                ],
                className="hero-section",
            ),
            dbc.Alert(
                [
                    html.P("Unable to load occupancy data.", className="mb-1 fw-semibold"),
                    html.P(error_message or "Unknown error", className="mb-0"),
                ],
                color="warning",
                className="unavailable-alert",
            ),
            html.P(
                [
                    "Data sourced from on-campus occupancy sensors via the Density API. ",
                    "Readings are collected every 30 minutes during gym operating hours ",
                    "(Mon–Fri 7 AM–11 PM, Sat 8 AM–6 PM, Sun 8 AM–11 PM PST). ",
                    "Values represent estimated percentage of maximum capacity (150 people).",
                ],
                className="footer-text text-center mb-4",
            ),
        ],
        fluid=True,
        className="pb-4",
        style={"maxWidth": "1400px"},
    )


def build_dashboard_layout(df: pd.DataFrame):
    insights = compute_insights(df)
    pivot = fetch.build_heatmap_pivot(df)
    avg_capacity = insights["avg_capacity"]

    return dbc.Container(
        [
            navbar(),
            html.Div(
                [
                    html.H1("When should you hit the gym?"),
                    html.P(
                        f"Occupancy trends from {insights['date_start']} to "
                        f"{insights['date_end']} · "
                        f"{insights['total_readings']} readings collected every 30 minutes"
                    ),
                ],
                className="hero-section",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        kpi_card(
                            "Overall Average",
                            f"{avg_capacity:.1f}%",
                            "Across all operating hours",
                        ),
                        lg=3,
                        md=6,
                        className="mb-3",
                    ),
                    dbc.Col(
                        kpi_card(
                            "Quietest Day",
                            insights["least_busy_day"][:3],
                            f"Avg. {insights['least_busy_day_avg']:.1f}% capacity",
                        ),
                        lg=3,
                        md=6,
                        className="mb-3",
                    ),
                    dbc.Col(
                        kpi_card(
                            "Busiest Day",
                            insights["most_busy_day"][:3],
                            f"Avg. {insights['most_busy_day_avg']:.1f}% capacity",
                        ),
                        lg=3,
                        md=6,
                        className="mb-3",
                    ),
                    dbc.Col(
                        kpi_card(
                            "Peak Hours",
                            "4–6 PM",
                            f"Avg. {insights['peak_hours_avg']:.1f}% capacity",
                        ),
                        lg=3,
                        md=6,
                        className="mb-3",
                    ),
                ],
                className="mb-2",
            ),
            html.P("Occupancy Trends", className="section-title mt-4"),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("Best Times to Visit"),
                                dbc.CardBody(
                                    [
                                        insight_block(
                                            "Least Busy Day",
                                            insights["least_busy_day"],
                                            f"Average {insights['least_busy_day_avg']:.1f}% capacity",
                                        ),
                                        insight_block(
                                            "Least Busy Hour",
                                            format_hour(insights["least_busy_hour"]),
                                            f"Average {insights['least_busy_hour_avg']:.1f}% capacity",
                                        ),
                                        insight_block(
                                            "Peak Period",
                                            "4:00 – 6:00 PM",
                                            f"Average {insights['peak_hours_avg']:.1f}% capacity",
                                        ),
                                        insight_block(
                                            "Most Busy Day",
                                            insights["most_busy_day"],
                                            f"Average {insights['most_busy_day_avg']:.1f}% capacity",
                                        ),
                                    ]
                                ),
                            ],
                            className="insights-card",
                        ),
                        lg=4,
                        className="mb-3",
                    ),
                    dbc.Col(
                        [
                            dbc.Card(
                                dbc.CardBody(
                                    dcc.Graph(
                                        figure=create_daily_average(df, avg_capacity),
                                        config={"displayModeBar": False},
                                    )
                                ),
                                className="chart-card",
                            )
                        ],
                        lg=8,
                    ),
                ],
                className="mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Graph(
                                    figure=create_hourly_average(df),
                                    config={"displayModeBar": False},
                                )
                            ),
                            className="chart-card",
                        ),
                        lg=4,
                        className="mb-3",
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Graph(
                                    figure=create_heatmap(pivot),
                                    config={"displayModeBar": False},
                                )
                            ),
                            className="chart-card",
                        ),
                        lg=4,
                        className="mb-3",
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Graph(
                                    figure=create_histogram(df),
                                    config={"displayModeBar": False},
                                )
                            ),
                            className="chart-card",
                        ),
                        lg=4,
                        className="mb-3",
                    ),
                ],
            ),
            html.Hr(className="my-4"),
            html.P(
                [
                    "Data sourced from on-campus occupancy sensors via the Density API. ",
                    "Readings are collected every 30 minutes during gym operating hours ",
                    "(Mon–Fri 7 AM–11 PM, Sat 8 AM–6 PM, Sun 8 AM–11 PM PST). ",
                    "Values represent estimated percentage of maximum capacity (150 people).",
                ],
                className="footer-text text-center mb-4",
            ),
        ],
        fluid=True,
        className="pb-4",
        style={"maxWidth": "1400px"},
    )


def create_layout():
    data, error_message = fetch.try_load_occupancy_data()
    if data is None:
        return build_unavailable_layout(error_message or "Unknown error")
    return build_dashboard_layout(data)


app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.FLATLY,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
    ],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server
app.layout = create_layout


if __name__ == "__main__":
    app.run(debug=True)
