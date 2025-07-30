import os
from datetime import datetime

from dotenv import load_dotenv
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()
url = os.getenv("DENSITY_API_URL")
api_key = os.getenv("DENSITY_API_KEY")
headers = {
    "Authorization": f"Bearer {api_key}"
}

filename = "rsf_gym_crowd_data.csv"
max_capacity = 150

# Google Sheets setup
def setup_google_sheets():
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    # Path to credentials file when running in GitHub Actions
    credentials_path = 'credentials.json'
    credentials = Credentials.from_service_account_file(
        credentials_path,
        scopes=scope
    )
    
    client = gspread.authorize(credentials)
    spreadsheet_name = 'RSF_DATA'
    spreadsheet = client.open(spreadsheet_name)
    worksheet = spreadsheet.sheet1
    return worksheet

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
        df.to_csv(filename, mode='a', index=False, header=not os.path.exists(filename))
        
        # Update Google Sheet
        try:
            worksheet = setup_google_sheets()
            # Check if headers exist, add them if not
            if worksheet.row_count == 0:
                worksheet.append_row(['timestamp', 'percentage_capacity'])
            # Add the new data
            worksheet.append_row([timestamp, f"{percentage_capacity:.2f}"])
            print(f"Data saved to CSV and Google Sheets for {timestamp}")
        except Exception as e:
            print(f"Error updating Google Sheets: {e}")
            print(f"Data saved to CSV only for {timestamp}")
    else:
        print(f"Error {response.status_code}: {response.text}")
        return None
    
if __name__ == "__main__":
    get_gym_crowd_data()