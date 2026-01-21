import requests
import json
from datetime import datetime

# --- CONFIGURATION ---
# 🔑 REPLACE THIS with your actual API Key from the portal
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

# 2026 Regular Session Code (usually 20261)
SESSION_CODE = 20261 

def test_calendar_endpoint(chamber):
    """
    Pings the Official LIS API for the Calendar list.
    """
    url = "https://lis.virginia.gov/Calendar/api/getcalendarlistasync"
    
    # The official API requires the key in the HEADER, not the URL
    headers = {
        "WebAPIKey": API_KEY,
        "Accept": "application/json"
    }
    
    params = {
        "sessionCode": SESSION_CODE,
        "chamberCode": chamber,  # 'H' for House, 'S' for Senate
    }

    print(f"📡 Pinging {chamber} Calendar API...")
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Success! Found {len(data)} calendar entries.")
            
            # Save to a file so we can inspect it easily
            filename = f"api_response_{chamber}.json"
            with open(filename, "w") as f:
                json.dump(data, f, indent=4)
            print(f"📝 Saved full response to {filename}")
            
            # Quick peek for HB1
            found_hb1 = False
            if isinstance(data, list):
                for entry in data:
                    # Depending on API structure, adjust key names (guessing standard ones)
                    # We print the first entry to understand the structure
                    if entry == data[0]:
                        print("\n🧐 First Entry Structure:")
                        print(entry)
                        
            return data
        elif resp.status_code == 401:
            print("❌ Authentication Failed. Check your API Key.")
        else:
            print(f"❌ Error {resp.status_code}: {resp.text}")
            
    except Exception as e:
        print(f"💥 Critical Error: {e}")

# --- RUN THE TEST ---
if __name__ == "__main__":
    print("--- STARTING API TEST ---")
    test_calendar_endpoint("H") # Test House
    print("\n")
    test_calendar_endpoint("S") # Test Senate
