import streamlit as st
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
CGI_BASE = "https://lis.virginia.gov/cgi-bin/legp604.exe"
SESSION_CGI = "261" # 2026 Regular
BILL_NUM = "HB1"

st.set_page_config(page_title="v2400 Raw HTML Audit", page_icon="📝", layout="wide")
st.title("📝 v2400: The 'Raw HTML' Audit")

session = requests.Session()

def run_audit():
    st.subheader(f"Fetching Raw HTML for {BILL_NUM} (Session {SESSION_CGI})...")
    
    url = f"{CGI_BASE}?{SESSION_CGI}+sum+{BILL_NUM}"
    st.write(f"Target URL: `{url}`")
    
    try:
        # Standard Browser Headers (Essential for Legacy Sites)
        h = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html'
        }
        
        r = session.get(url, headers=h, timeout=5)
        
        if r.status_code == 200:
            html = r.text
            
            st.success("✅ HTML Downloaded!")
            
            # 1. SMART SEARCH
            # We look for keywords and print the context around them
            keywords = ["Committee", "Referred", "Privileges", "Agriculture", "Finance"]
            
            st.info("🔎 **Keyword Scan:**")
            found_something = False
            
            for k in keywords:
                if k in html:
                    found_something = True
                    # Find index
                    idx = html.find(k)
                    # Grab context (100 chars before and after)
                    start = max(0, idx - 100)
                    end = min(len(html), idx + 100)
                    snippet = html[start:end].replace("<", "&lt;").replace(">", "&gt;")
                    
                    st.markdown(f"**Found '{k}':**")
                    st.code(snippet, language="html")
                    
            if not found_something:
                st.warning("❌ No keywords found. The page might be an error page or empty.")
            
            # 2. RAW DUMP (In an expander so it doesn't clutter)
            with st.expander("View Full Raw HTML"):
                st.code(html)
                
            # 3. BEAUTIFUL SOUP PARSE (Attempt to find the structure)
            soup = BeautifulSoup(html, 'html.parser')
            text_clean = soup.get_text(separator=' | ', strip=True)
            with st.expander("View Cleaned Text"):
                st.write(text_clean)
                
        else:
            st.error(f"❌ HTTP Error: {r.status_code}")
            
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run HTML Audit"):
    run_audit()
