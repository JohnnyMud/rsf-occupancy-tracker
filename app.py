from dash import Dash, html, dcc, callback, Output, Input, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import data_fetch as fetch

# Load in data
df = fetch.data
pivot = fetch.pivot_table
avg_capacity = df['percentage_capacity'].mean()

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
                html.P("• Least busy day: Sunday (avg. 54% capacity)"),
                html.P("• Least busy hours: 7 AM (avg. 43% capacity)"),
                html.P("• Most busy hours: 4-6 PM (avg. 85% capacity)"),
                html.P("• Most busy day: Tuesday (avg. 73% capacity)"),
            ], style={'padding': '20px', 'backgroundColor': '#f8f9fa', 'borderRadius': '10px'})
        ], style={'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '20px'}),
        html.Div([
            dcc.Graph(figure=create_daily_average()),
            dcc.Graph(figure=create_histogram())
        ], style={'width': '70%', 'display': 'inline-block'})
    ]),

    dash_table.DataTable(data=df.to_dict('records'), page_size=10),
    
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
