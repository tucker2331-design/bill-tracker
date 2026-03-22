import requests
from bs4 import BeautifulSoup
import re
import json

def test_house_js_bypass(url):
    print(f"\n--- TESTING HOUSE JS BYPASS ---")
    print(f"Targeting: {url}")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    res = requests.get(url, headers=headers)
    
    if res.status_code != 200:
        print(f"Failed to connect. Status: {res.status_code}")
        return
        
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # TACTIC 1: Look for embedded JSON state (Common in Next.js / Nuxt.js)
    script_tags = soup.find_all('script')
    found_bills = set()
    
    for script in script_tags:
        if script.string and ('{"' in script.string or 'SB' in script.string or 'HB' in script.string):
            # Use Regex to rip out anything that looks like a bill number from the raw script payload
            matches = re.findall(r'\b([HS][A-Za-z]{0,2}\s*\d+)', script.string)
            found_bills.update([m.replace(" ", "").upper() for m in matches])
            
    # TACTIC 2: Raw text fallback (in case they server-side rendered parts of it)
    text = soup.get_text(separator=' ')
    matches = re.findall(r'\b([HS][A-Za-z]{0,2}\s*\d+)', text)
    found_bills.update([m.replace(" ", "").upper() for m in matches])
    
    print(f"Bills Extracted: {sorted(list(found_bills))}")
    if "SB53" in found_bills:
        print("✅ SUCCESS: Bypassed JS and found the target bills.")
    else:
        print("❌ FAILED: The bills are locked behind an API endpoint.")

# Testing the URL from your screenshot
test_house_js_bypass("https://house.vga.virginia.gov/subcommittees/H24001/agendas/5606")
