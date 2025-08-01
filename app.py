from dash import Dash, html, dcc, callback, Output, Input, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

import data_fetch as fetch

# Load in data
df = fetch.data
pivot = fetch.pivot_table
avg_capacity = df['percentage_capacity'].mean()

# Calculate key statistics
weekday_avgs = df.groupby('weekday')['percentage_capacity'].mean().sort_values()
hourly_avgs = df.groupby('hour')['percentage_capacity'].mean().sort_values()

least_busy_day = weekday_avgs.index[0]
least_busy_day_avg = weekday_avgs.iloc[0]
most_busy_day = weekday_avgs.index[-1]
most_busy_day_avg = weekday_avgs.iloc[-1]

least_busy_hour = hourly_avgs.index[0]
least_busy_hour_avg = hourly_avgs.iloc[0]
most_busy_hour = hourly_avgs.index[-1]
most_busy_hour_avg = hourly_avgs.iloc[-1]

# Calculate peak hours (4-6 PM average)
peak_hours_avg = df[df['hour'].isin([16, 17, 18])]['percentage_capacity'].mean()

app = Dash()

# Create visualizations
def create_heatmap():
    fig = px.imshow(pivot,
                    labels=dict(x="Hour", y="Day", color="Occupancy %"),
                    color_continuous_scale="RdYlGn_r",
                    aspect="auto")
    fig.update_layout(title="Average Gym Occupancy by Day and Hour",
                     xaxis_title="Hour of Day",
                     yaxis_title="Day of Week")
    return fig

def create_daily_average():
    daily_avg = df.groupby('weekday')['percentage_capacity'].mean().reset_index()
    fig = px.bar(daily_avg, x='weekday', y='percentage_capacity',
                 labels={'percentage_capacity': 'Average Occupancy %', 'weekday': 'Day of Week'},
                 color='percentage_capacity',
                 color_continuous_scale="RdYlGn_r")
    fig.update_layout(title="Average Gym Occupancy by Day of Week",
                     xaxis_title="Day of Week",
                     yaxis_title="Average Occupancy %")
    fig.add_hline(y=avg_capacity, line_dash="dash", line_color='red',
                  annotation_text=f"Average: {avg_capacity:.2f}%",
                  annotation_position='top left')
    fig.update_xaxes(categoryorder='total ascending')
    return fig

def create_hourly_average():
    hourly_avg = df.groupby('hour')['percentage_capacity'].mean().reset_index()
    fig = px.line(hourly_avg, x='hour', y='percentage_capacity',
                  labels={'percentage_capacity': 'Average Occupancy %', 'hour': 'Hour of Day'},
                  markers=True)
    fig.update_layout(title="Average Gym Occupancy by Hour of Day",
                     xaxis_title="Hour of Day",
                     yaxis_title="Average Occupancy %")
    return fig

def create_histogram():
    fig = px.histogram(df, x='percentage_capacity')
    fig.update_layout(title="Distribution of Gym Occupancy",
                     xaxis_title="Occupancy %",
                     yaxis_title="Count")
    return fig

#Data Distribution and Averages
app.layout = html.Div([
    html.H1(children='RSF Gym Occupancy Tracker', 
            style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '30px'}),
    
    html.Div([
        html.Div([
            html.H3("Best Times to Visit", style={'textAlign': 'center'}),
            html.Div([
                html.P(f"• Least busy day: {least_busy_day} (avg. {least_busy_day_avg:.1f}% capacity)"),
                html.P(f"• Least busy hours: {least_busy_hour} (avg. {least_busy_hour_avg:.1f}% capacity)"),
                html.P(f"• Most busy hours: 4-6 PM (avg. {peak_hours_avg:.1f}% capacity)"),
                html.P(f"• Most busy day: {most_busy_day} (avg. {most_busy_day_avg:.1f}% capacity)"),
            ], style={'padding': '20px', 'backgroundColor': '#f8f9fa', 'borderRadius': '10px'})
        ], style={'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '20px'}),
        
        html.Div([
            dcc.Graph(figure=create_daily_average()),
            dcc.Graph(figure=create_histogram())
        ], style={'width': '70%', 'display': 'inline-block'})
    ]),
    
    html.Div([
        html.Div([
            dcc.Graph(figure=create_hourly_average())
        ], style={'width': '50%', 'display': 'inline-block'}),
        
        html.Div([
            dcc.Graph(figure=create_heatmap())
        ], style={'width': '50%', 'display': 'inline-block'})
    ]),
    
    html.Div([
        html.P("Data is collected every 30 minutes during gym operating hours.",
               style={'textAlign': 'center', 'color': '#666', 'fontSize': '14px'})
    ], style={'marginTop': '30px'})
])

if __name__ == '__main__':
    app.run(debug=True)
