import os
import json
import requests
import gspread
from google.oauth2.service_account import Credentials

print("🚀 Waking up Ghost Worker...")

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}
TARGET_URL = "https://lis.virginia.gov/Legislation/api/getlegislationsessionlistasync"
SPREADSHEET_ID = "1566pCv70iQ7YkTQK71RfYerciK-ukW-QdblTu2-Prfw"

def run_update():
    # 1. Authenticate with Google
    print("🔐 Authenticating with Google Cloud...")
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        print("❌ ERROR: GCP_CREDENTIALS secret is missing from GitHub!")
        return
    
    creds_dict = json.loads(creds_json)
    credentials = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(credentials)
    worksheet = gc.open_by_key(SPREADSHEET_ID).sheet1

    # 2. Pull State API Data
    print("📡 Pinging Virginia Master REST API...")
    response = requests.get(TARGET_URL, headers=HEADERS, params={"sessionCode": "20261"}, timeout=15)
    response.raise_for_status()
    all_bills = response.json().get("Legislations", [])
    print(f"✅ Found {len(all_bills)} bills.")

    # 3. Format and Blast to Sheets
    print("📝 Formatting data and wiping old database...")
    sheet_data = [["Bill Number", "Title", "Current Status"]] 
    
    for item in all_bills:
        bill_number = item.get("LegislationNumber", "Unknown")
        title = item.get("Description", "No Title")
        status = item.get("LegislationStatus", "Unknown") # FIXED THE STATUS KEY!
        sheet_data.append([bill_number, title, status])
    
    worksheet.clear() # Wipes the old data
    worksheet.update(values=sheet_data, range_name="A1")
    print("🎉 DATABASE BRIDGE COMPLETE! Sheets updated.")

if __name__ == "__main__":
    run_update()
