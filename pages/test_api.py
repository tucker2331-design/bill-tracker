import streamlit as st
import requests
import re
import concurrent.futures
from bs4 import BeautifulSoup

st.set_page_config(page_title="v100 Bill Hunter", page_icon="📜", layout="wide")
st.title("📜 v100: Standalone Bill Hunter")

# --- CONFIGURATION ---
# We bypass the "Search" entirely by knowing where to look.
# These are the permanent IDs for major committees.
COMMITTEES = [
    # HOUSE
    {"name": "House Appropriations", "url": "https://house.vga.virginia.gov/committees/H02"},
    {"name": "House Finance", "url": "https://house.vga.virginia.gov/committees/H09"},
    {"name": "House Courts of Justice", "url": "https://house.vga.virginia.gov/committees/H08"},
    {"name": "House Commerce & Energy", "url": "https://house.vga.virginia.gov/committees/H11"},
    {"name": "House Education", "url": "https://house.vga.virginia.gov/committees/H07"},
    {"name": "House Health & Human Services", "url": "https://house.vga.virginia.gov/committees/H13"},
    {"name": "House Public Safety", "url": "https://house.vga.virginia.gov/committees/H18"},
    # SENATE (Note: Senate URLs are often different/older, using LIS direct links if possible)
    {"name": "Senate Commerce & Labor", "url": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S03"},
    {"name": "Senate Courts of Justice", "url": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S04"},
    {"name": "Senate Finance & Appropriations", "url": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S05"},
    {"name": "Senate Education & Health", "url": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S02"},
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

def get_bills_from_url(url):
    """
    Visits the URL and regex-scrapes for bill numbers.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        # Regex to find HB1234, SB50, etc.
        # Matches "HB" or "S.B." followed optionally by dots/spaces, then numbers
        pattern = r'\b([H|S]\.?[B|J|R]\.?)\s*(\d+)\b'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        # Clean and sort
        bills = set()
        for p, n in matches:
            prefix = p.upper().replace(".", "").strip()
            bills.add(f"{prefix}{n}")
            
        # Sort nicely (HB1 before HB100)
        def sort_key(b):
            # Split letters and numbers
            match = re.match(r"([A-Z]+)(\d+)", b)
            if match: return match.group(1), int(match.group(2))
            return b, 0
            
        return sorted(list(bills), key=sort_key)
    except Exception as e:
        return []

# --- MAIN APP ---

if st.button("🔄 Scan All Committees", type="primary"):
    
    results = {}
    
    # Run in parallel for speed
    with st.status("Scanning Committee Dockets...", expanded=True) as status:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_name = {executor.submit(get_bills_from_url, c['url']): c['name'] for c in COMMITTEES}
            
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    bills = future.result()
                    results[name] = bills
                    st.write(f"✅ Scanned {name}")
                except:
                    results[name] = []
                    
        status.update(label="Scan Complete", state="complete", expanded=False)

    # --- DISPLAY ---
    st.divider()
    
    # Create columns for layout
    cols = st.columns(3)
    
    # Distribute results across columns
    for i, (name, bills) in enumerate(results.items()):
        col = cols[i % 3]
        with col:
            with st.container(border=True):
                st.markdown(f"### {name}")
                
                # Find the URL for the button
                url = next(c['url'] for c in COMMITTEES if c['name'] == name)
                
                if bills:
                    st.success(f"**{len(bills)} Bills Found**")
                    st.markdown(", ".join(bills))
                else:
                    st.caption("No bills listed on docket.")
                
                st.link_button("View Docket", url)

else:
    st.info("Click the button to scan major committees for active bills.")
