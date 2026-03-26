import requests
import json

print("🚀 Waking up Naked Diagnostic Probe...")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}
URL = "https://lis.virginia.gov/Session/api/GetSessionListAsync"

print(f"📡 Pinging {URL}...")

try:
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'})
    
    res = session.get(URL, headers=HEADERS, timeout=15)
    
    print(f"HTTP Status Code: {res.status_code}")
    
    if res.status_code == 200:
        print("✅ Connection Successful. Parsing Raw JSON Payload:")
        try:
            data = res.json()
            # Print the entire JSON structure beautifully so we can read the exact keys
            print(json.dumps(data, indent=2))
        except Exception as json_err:
            print(f"❌ Failed to parse JSON. Raw text returned by state:")
            print(res.text)
    else:
        print(f"❌ Connection Failed. State server returned: {res.status_code}")
        print("Raw Response Headers:")
        print(res.headers)
        print("Raw Response Text:")
        print(res.text)

except Exception as e:
    print(f"🚨 Fatal Network Exception: {e}")
