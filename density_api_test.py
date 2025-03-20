import requests
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

# Get configuration from environment variables
load_dotenv()

# API endpoint for getting the gym crowd data
url = os.getenv("DENSITY_API_URL")
api_key = os.getenv("DENSITY_API_KEY")
max_capacity = int(os.getenv("MAX_CAPACITY", 150))  # 150 as default if not set

headers = {
    "Authorization": f"Bearer {api_key}"
}

filename = "rsf_gym_crowd_data.csv"

# Function to get and save the gym crowd data
def get_gym_crowd_data():
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()

        # Get the relevant data from the response
        current_count = data['count']
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        percentage_capacity = (current_count / max_capacity) * 100

        # Create a DataFrame record for the current timestamp
        df = pd.DataFrame({'timestamp': [timestamp], 'percentage_capacity': [percentage_capacity]})

        # Append the data to the CSV file
        df.to_csv(filename, mode='a', index=False, header=not os.path.exists(filename))

        print(f"saved data for {timestamp}")
    else:
        print(f"Error {response.status_code}: {response.text}")
        return None
    
get_gym_crowd_data()