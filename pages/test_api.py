import streamlit as st
import requests
import re
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
BASE_URL = "https://lis.virginia.gov"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

st.set_page_config(page_title="v305 Suspect Lineup", page_icon="🕵️‍♂️", layout="wide")
st.title("🕵️‍♂️ v305: The Suspect Lineup")

session = requests.Session()

def run_filter():
    st.write("📡 Scanning JavaScript for high-value targets...")
    try:
        # 1. Get JS URL
        resp = session.get(f"{BASE_URL}/session-details/20261/committee-information/H18/committee-details", headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        scripts = [s.get('src') for s in soup.find_all('script') if s.get('src') and "static/js/" in s.get('src')]
        
        if not scripts:
            st.error("❌ No scripts found.")
            return

        # 2. Download & Filter
        suspects = []
        keywords = ["Docket", "Agenda", "Event", "Meeting", "Collection", "Bill", "Legislation"]
        
        for script_url in scripts:
            full_url = f"{BASE_URL}{script_url}"
            js_resp = session.get(full_url, headers=HEADERS, timeout=10)
            
            if js_resp.status_code == 200:
                content = js_resp.text
                # Find all API calls: Service/api/Action
                matches = re.findall(r'([a-zA-Z0-9_]+)/api/([a-zA-Z0-9_]+)', content)
                
                for service, action in matches:
                    # FILTER: Only keep it if it sounds interesting
                    if any(k in action for k in keywords) or any(k in service for k in keywords):
                        suspects.append(f"{service}/api/{action}")
        
        # 3. Display
        st.divider()
        if suspects:
            st.success(f"🎯 Found {len(suspects)} High-Value Candidates:")
            
            # Remove duplicates and sort
            unique_suspects = sorted(list(set(suspects)))
            
            for s in unique_suspects:
                st.code(s, language="text")
                
            st.info("👆 The 'Golden Endpoint' is likely in this list. Tell me which one looks like 'GetDocket'!")
        else:
            st.warning("⚠️ No endpoints matched our keywords.")

    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Identify Suspects"):
    run_filter()
