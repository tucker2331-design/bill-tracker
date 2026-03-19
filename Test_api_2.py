import requests
import json
import time

print("🚀 Initiating API Parameter Cracker...")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}
TARGET_URL = "https://lis.virginia.gov/Calendar/api/getdocketlistbycommitteenumberasync"

# The 6 most likely variations based on VA LIS quirks
test_combinations = [
    # Test 1: Full Session + H + H02 (Postman Example Format)
    {"sessionCode": "20261", "chamberCode": "H", "committeeNumber": "H02"},
    
    # Test 2: Full Session + H + 02 (Stripped prefix)
    {"sessionCode": "20261", "chamberCode": "H", "committeeNumber": "02"},
    
    # Test 3: Full Session + H + 2 (Raw integer)
    {"sessionCode": "20261", "chamberCode": "H", "committeeNumber": "2"},
    
    # Test 4: Short Session + H + H02 (Matches Schedule API behavior)
    {"sessionCode": "261", "chamberCode": "H", "committeeNumber": "H02"},
    
    # Test 5: Short Session + H + 02
    {"sessionCode": "261", "chamberCode": "H", "committeeNumber": "02"},
    
    # Test 6: Short Session + H + 2
    {"sessionCode": "261", "chamberCode": "H", "committeeNumber": "2"}
]

cracked = False

for i, params in enumerate(test_combinations):
    print(f"\n[Test {i+1}/6] Firing payload: {params}")
    
    try:
        response = requests.get(TARGET_URL, headers=HEADERS, params=params, timeout=5)
        
        # Check if the server threw an HTML error page (the trap)
        if "text/html" in response.headers.get("Content-Type", ""):
            print(f"❌ FAILED: Server returned HTML trap (Status {response.status_code})")
        
        elif response.status_code == 200:
            print("\n✅ LOCK CRACKED! STATUS 200 OK")
            print("=" * 50)
            print(f"WINNING PARAMETERS: {params}")
            print(f"EXACT URL FIRED: {response.url}")
            print("=" * 50)
            print("JSON PAYLOAD PREVIEW:")
            
            data = response.json()
            # Just print the first 500 characters of the JSON to prove we got it
            print(json.dumps(data, indent=2)[:500] + "\n... [DATA TRUNCATED]")
            
            cracked = True
            break # Stop firing, we won
            
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ Connection Error: {e}")
        
    # Politeness delay to avoid tripping state firewalls
    time.sleep(1.5)

if not cracked:
    print("\n💀 ALL TESTS FAILED. The API likely requires the secret 'sessionID' GUID string.")
