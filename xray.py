import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

print("\n--- TESTING NETWORK ARMOR & DEAD LETTER QUEUE ---")

# --- 1. The Network Armor (Smart Retry, No Blind Sleeping) ---
def get_armored_session():
    session = requests.Session()
    # Spoofing a real browser so the state firewall doesn't block "python-requests"
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'})
    
    # Smart Retries: Only pauses IF the server throws a 429 (Too Many Requests) or a 500-level server crash.
    # It does NOT slow down normal, successful requests.
    retries = Retry(
        total=3, 
        backoff_factor=0.5, 
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# --- 2. The Dead Letter Queue (DLQ) Routing ---
def route_vote(csv_committee_name, is_pdf_corrupt=False):
    # Simulated strictly-mapped Lexicon
    LEXICON = {
        "House Committee on Transportation": ["transportation"],
        "Senate Committee on Finance and Appropriations": ["finance and appropriations", "finance"]
    }
    
    # DLQ Trigger 1: The Scraper crashes on a bad/scanned PDF
    if is_pdf_corrupt:
        return "⚠️ [Agenda unreadable - Manual check required]"

    outcome_lower = csv_committee_name.lower()
    matched = None
    
    # Attempt strict match
    for api_name, aliases in LEXICON.items():
        if any(alias in outcome_lower for alias in aliases):
            matched = api_name
            break
            
    # DLQ Trigger 2: The Rogue Clerk (Unmapped Name)
    if not matched:
        # Instead of generic Ledger, it flags the exact weird name the clerk typed
        return f"⚠️ [Unmapped] {csv_committee_name} (Ledger)"
        
    return matched

# --- EXECUTE TESTS ---
print("Test A: Armored Network Request (Target: house.vga.virginia.gov)")
try:
    http = get_armored_session()
    start = time.time()
    # Enforcing a strict 5-second timeout so a dead server never hangs your GitHub Action
    res = http.get("https://house.vga.virginia.gov", timeout=5) 
    print(f"✅ Success! Status: {res.status_code}. Time taken: {round(time.time() - start, 2)}s")
except Exception as e:
    print(f"❌ Failed gracefully (Timeout or Blocked): {e}")

print("\nTest B: Dead Letter Queue (DLQ) Routing")
print(f"Scenario 1 (Perfect Match): 'Reported from Transportation' -> {route_vote('Reported from Transportation')}")
print(f"Scenario 2 (Rogue Clerk): 'Reported from Ad-Hoc AI Sub' -> {route_vote('Reported from Ad-Hoc AI Sub')}")
print(f"Scenario 3 (Corrupt PDF): 'House Transportation' -> {route_vote('House Transportation', is_pdf_corrupt=True)}")
