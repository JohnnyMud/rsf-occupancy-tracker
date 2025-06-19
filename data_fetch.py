import pandas as pd
import rsf_data_collector as rsf

def get_df():
    sheet = rsf.setup_google_sheets()
    values = sheet.get_all_values()
    headers = values[0]
    rsf_df = pd.DataFrame(values[1:], columns=headers)
    return rsf_df

spring_break_end = pd.Timestamp('2025-03-31')
end_of_semester = pd.Timestamp('2025-05-04')

def filter_gym_data():
    #Only keep data points recorded after spring break (>= 31st)
    df = get_df()
    date_format = '%m/%d/%Y %I:%M:%p'
    #Convert columns to consistent datatypes
    df['pst_timestamp'] = pd.to_datetime(df['pst_timestamp'], format=date_format)
    df['percentage_capacity'] = df['percentage_capacity'].astype(float).round()
    df = df[(df['pst_timestamp'] >= spring_break_end) & (df['pst_timestamp'] <= end_of_semester)]
    #Only keep data points recorded within hours of operation (due to issues with github workflow)
    df = df[(df['pst_timestamp'].dt.hour >= 7) & (df['pst_timestamp'].dt.hour < 23)]
    #Remove data points where the gym is 0% full and over 100% full
    df['percentage_capacity'] = df['percentage_capacity'].clip(lower=1, upper=100)
    #Drop UTC timestamp
    df = df.drop(columns=['timestamp'])
    return df

data = filter_gym_data()

# Average occupancy by hour
data['pst_hour'] = [f'{tstamp.hour} AM' if tstamp.hour < 12 else '12 PM' if tstamp.hour == 12 else f'{tstamp.hour - 12} PM' for tstamp in data['pst_timestamp']]
avg_by_hour = data.groupby('pst_hour')['percentage_capacity'].mean().sort_values()

# Average occupancy by day of week
data['weekday'] = data['pst_timestamp'].dt.day_name()
avg_by_weekday = data.groupby('weekday')['percentage_capacity'].mean().sort_values()

#24hr format hour
data['hour'] = [i.hour for i in data['pst_timestamp']]

#Make colums ordered nicely
data = data[['pst_timestamp', 'pst_hour', 'weekday', 'hour', 'percentage_capacity']]

pivot_table = data.pivot_table(index='weekday', columns='hour', values='percentage_capacity', aggfunc='mean')
pivot_table.columns = [f'{hour} AM' if hour < 12 else '12 PM' if hour == 12 else f'{hour - 12} PM' for hour in pivot_table.columns]