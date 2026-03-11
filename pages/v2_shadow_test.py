import requests
import json

print("🚀 Initiating Phase 1: LIS Legislation Payload Test...")

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# ⚠️ Architect: Paste the exact URL from your Postman 'Legislation' folder here:
TARGET_URL = "INSERT_POSTMAN_URL_HERE" 

# We will test with a known high-profile bill (e.g., HB42 or SB10)
# You may need to adjust the parameter keys (e.g., 'billNumber', 'legislationId') 
# based on what Postman shows is required.
PARAMS = {
    "sessionCode": "20261", 
    "billNumber": "HB42" 
}

try:
    print(f"📡 Pinging LIS Legislation API for HB42...")
    response = requests.get(TARGET_URL, headers=HEADERS, params=PARAMS, timeout=10)
    
    if response.status_code == 200:
        print("✅ SUCCESS! Vault breached. Payload received:\n")
        
        # Pretty-print the JSON so we can analyze the schema
        data = response.json()
        print(json.dumps(data, indent=4))
        
    elif response.status_code == 204:
        print("⚠️ STATUS 204: The endpoint is correct, but the bill was not found or the payload is empty.")
    else:
        print(f"❌ ERROR: Server rejected the request. Status Code: {response.status_code}")
        print("Response Text:", response.text)

except Exception as e:
    print(f"🛑 NETWORK CRASH: {e}")
