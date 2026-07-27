import dash_bootstrap_components as dbc
import plotly.express as px
from dash import Dash, dcc, html

import data_fetch as fetch

DAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

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

df = fetch.data
pivot = fetch.pivot_table
avg_capacity = df["percentage_capacity"].mean()

weekday_avgs = df.groupby("weekday")["percentage_capacity"].mean().reindex(DAY_ORDER).dropna()
hourly_avgs = df.groupby("hour")["percentage_capacity"].mean().sort_values()

least_busy_day = weekday_avgs.idxmin()
least_busy_day_avg = weekday_avgs.min()
most_busy_day = weekday_avgs.idxmax()
most_busy_day_avg = weekday_avgs.max()

least_busy_hour = hourly_avgs.idxmin()
least_busy_hour_avg = hourly_avgs.min()
peak_hours_avg = df[df["hour"].isin([16, 17, 18])]["percentage_capacity"].mean()

date_start = df["pst_timestamp"].min().strftime("%b %d, %Y")
date_end = df["pst_timestamp"].max().strftime("%b %d, %Y")
total_readings = len(df)


def format_hour(hour: int) -> str:
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"


def apply_chart_style(fig, height=380):
    fig.update_layout(**CHART_LAYOUT, height=height)
    return fig


def create_heatmap():
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


def create_daily_average():
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


def create_hourly_average():
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


def create_histogram():
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


app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.FLATLY,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
    ],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server

app.layout = dbc.Container(
    [
        dbc.Navbar(
            dbc.Container(
                [
                    html.Div(
                        [
                            html.Span("RSF Occupancy Tracker", className="navbar-brand fw-bold text-white"),
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
        ),
        html.Div(
            [
                html.H1("When should you hit the gym?"),
                html.P(
                    f"Occupancy trends from {date_start} to {date_end} · "
                    f"· readings collected every 30 minutes"
                ),
            ],
            className="hero-section",
        ),
        dbc.Row(
            [
                dbc.Col(
                    kpi_card("Overall Average", f"{avg_capacity:.1f}%", "Across all operating hours"),
                    lg=3,
                    md=6,
                    className="mb-3",
                ),
                dbc.Col(
                    kpi_card("Quietest Day", least_busy_day[:3], f"Avg. {least_busy_day_avg:.1f}% capacity"),
                    lg=3,
                    md=6,
                    className="mb-3",
                ),
                dbc.Col(
                    kpi_card("Busiest Day", most_busy_day[:3], f"Avg. {most_busy_day_avg:.1f}% capacity"),
                    lg=3,
                    md=6,
                    className="mb-3",
                ),
                dbc.Col(
                    kpi_card("Peak Hours", "4–6 PM", f"Avg. {peak_hours_avg:.1f}% capacity"),
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
                                        least_busy_day,
                                        f"Average {least_busy_day_avg:.1f}% capacity",
                                    ),
                                    insight_block(
                                        "Least Busy Hour",
                                        format_hour(least_busy_hour),
                                        f"Average {least_busy_hour_avg:.1f}% capacity",
                                    ),
                                    insight_block(
                                        "Peak Period",
                                        "4:00 – 6:00 PM",
                                        f"Average {peak_hours_avg:.1f}% capacity",
                                    ),
                                    insight_block(
                                        "Most Busy Day",
                                        most_busy_day,
                                        f"Average {most_busy_day_avg:.1f}% capacity",
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
                            dbc.CardBody(dcc.Graph(figure=create_daily_average(), config={"displayModeBar": False})),
                            className="chart-card",
                        ),
                        dbc.Card(
                            dbc.CardBody(dcc.Graph(figure=create_histogram(), config={"displayModeBar": False})),
                            className="chart-card",
                        ),
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
                        dbc.CardBody(dcc.Graph(figure=create_hourly_average(), config={"displayModeBar": False})),
                        className="chart-card",
                    ),
                    lg=6,
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(dcc.Graph(figure=create_heatmap(), config={"displayModeBar": False})),
                        className="chart-card",
                    ),
                    lg=6,
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


if __name__ == "__main__":
    app.run(debug=True)
