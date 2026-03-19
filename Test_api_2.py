import requests
import json
import time

print("🚀 Initiating API Parameter Cracker...")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}
TARGET_URL = "https://lis.virginia.gov/Calendar/api/getdocketlistbycommitteenumberasync"

# We test the two session codes (short and long), the chamber code, and the three ways a committee number could be formatted.
test_combinations = []
for sess in ["261", "20261"]:
    for comm in ["H02", "02", "2"]:
        # Test with Chamber Code Explicitly set to H
        test_combinations.append({"sessionCode": sess, "chamberCode": "H", "committeeNumber": comm})
        # Test without Chamber Code (sometimes they only want the committee ID)
        test_combinations.append({"sessionCode": sess, "committeeID": comm})
        test_combinations.append({"sessionCode": sess, "committeeId": comm}) # Test lowercase 'd'

cracked = False

for i, params in enumerate(test_combinations):
    print(f"\n[Test {i+1}/{len(test_combinations)}] Firing payload: {params}")
    
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
            print(json.dumps(data, indent=2)[:500] + "\n... [DATA TRUNCATED]")
            
            cracked = True
            break
            
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ Connection Error: {e}")
        
    time.sleep(1.5)

if not cracked:
    print("\n💀 ALL TESTS FAILED. The API is locked down. Proceed to Hybrid Architecture.")
