import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html

import analytics
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
    hourly_avg = (
        df.groupby("hour")["percentage_capacity"]
        .mean()
        .reindex(fetch.OPERATING_HOUR_BUCKETS)
        .reset_index()
    )
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
                html.P(
                    subtitle,
                    className="text-muted mb-0",
                    style={"fontSize": "0.8rem"},
                ),
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


def _avg_with_sample(avg: float | None, count: int) -> str:
    if avg is None:
        return "Insufficient data"
    return f"Average {avg:.1f}% capacity · {analytics.sample_size_label(count)}"


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
                    html.P(
                        "Unable to load occupancy data.",
                        className="mb-1 fw-semibold",
                    ),
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
    insights = analytics.compute_insights(df)
    pivot = fetch.build_heatmap_pivot(df)
    avg_capacity = insights.avg_capacity
    missing_days_text = (
        f"Missing days: {', '.join(insights.missing_days)}"
        if insights.missing_days
        else "All weekdays represented"
    )

    return dbc.Container(
        [
            navbar(),
            html.Div(
                [
                    html.H1("When should you hit the gym?"),
                    html.P(
                        f"Occupancy trends from {insights.date_start} to "
                        f"{insights.date_end} · "
                        f"{insights.total_readings} readings during operating hours"
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
                            f"{analytics.sample_size_label(insights.total_readings)} · "
                            f"{insights.date_start} – {insights.date_end}",
                        ),
                        lg=3,
                        md=6,
                        className="mb-3",
                    ),
                    dbc.Col(
                        kpi_card(
                            "Quietest Day",
                            insights.least_busy_day[:3]
                            if insights.least_busy_day
                            else "—",
                            _avg_with_sample(
                                insights.least_busy_day_avg,
                                insights.least_busy_day_n,
                            ),
                        ),
                        lg=3,
                        md=6,
                        className="mb-3",
                    ),
                    dbc.Col(
                        kpi_card(
                            "Busiest Day",
                            insights.most_busy_day[:3]
                            if insights.most_busy_day
                            else "—",
                            _avg_with_sample(
                                insights.most_busy_day_avg,
                                insights.most_busy_day_n,
                            ),
                        ),
                        lg=3,
                        md=6,
                        className="mb-3",
                    ),
                    dbc.Col(
                        kpi_card(
                            "Peak Hours",
                            insights.peak_period_label,
                            _avg_with_sample(
                                insights.peak_period_avg,
                                insights.peak_period_n,
                            ),
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
                                            insights.least_busy_day or "Insufficient data",
                                            _avg_with_sample(
                                                insights.least_busy_day_avg,
                                                insights.least_busy_day_n,
                                            ),
                                        ),
                                        insight_block(
                                            "Least Busy Hour",
                                            format_hour(insights.least_busy_hour)
                                            if insights.least_busy_hour is not None
                                            else "Insufficient data",
                                            _avg_with_sample(
                                                insights.least_busy_hour_avg,
                                                insights.least_busy_hour_n,
                                            ),
                                        ),
                                        insight_block(
                                            "Peak Period",
                                            insights.peak_period_label,
                                            _avg_with_sample(
                                                insights.peak_period_avg,
                                                insights.peak_period_n,
                                            ),
                                        ),
                                        insight_block(
                                            "Most Busy Day",
                                            insights.most_busy_day or "Insufficient data",
                                            _avg_with_sample(
                                                insights.most_busy_day_avg,
                                                insights.most_busy_day_n,
                                            ),
                                        ),
                                        html.P(
                                            missing_days_text,
                                            className="text-muted mb-0 mt-3",
                                            style={"fontSize": "0.8rem"},
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
                    "Values represent estimated percentage of maximum capacity (150 people). ",
                    f"Analysis window: {insights.date_start} – {insights.date_end} "
                    f"({analytics.sample_size_label(insights.total_readings)}).",
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
    try:
        return build_dashboard_layout(data)
    except Exception as exc:
        return build_unavailable_layout(str(exc))


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
