import streamlit as st
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
# We use the specific code for House Privileges & Elections
TARGET_URL = "https://lis.virginia.gov/session-details/20261/committee-information/H18/committee-details"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

st.set_page_config(page_title="v205 Raw Inspector", page_icon="🔬", layout="wide")
st.title("🔬 v205: The Raw Source Inspector")
st.markdown(f"**Target:** [{TARGET_URL}]({TARGET_URL})")

if st.button("🔴 Fetch Raw HTML"):
    try:
        # 1. THE FETCH
        st.write("📡 Fetching...")
        resp = requests.get(TARGET_URL, headers=HEADERS, timeout=10)
        
        if resp.status_code == 200:
            raw_html = resp.text
            st.success("✅ Page Downloaded Successfully")
            
            # 2. THE SEARCH
            st.divider()
            st.subheader("🔎 Search the Source Code")
            search_term = st.text_input("Find text (e.g., 'Docket', 'January'):", value="Docket")
            
            if search_term:
                count = raw_html.count(search_term)
                if count > 0:
                    st.success(f"🎉 FOUND! The word '{search_term}' appears {count} times.")
                    st.info("This means we CAN scrape it!")
                else:
                    st.error(f"❌ NOT FOUND. The word '{search_term}' is not in the source code.")
                    st.warning("This implies it is loaded by JavaScript.")

            # 3. THE EVIDENCE
            st.divider()
            st.subheader("📜 Raw HTML Dump")
            st.text_area("Source Code:", value=raw_html, height=600)
            
        else:
            st.error(f"Failed to load page. Status: {resp.status_code}")
            
    except Exception as e:
        st.error(f"Connection Error: {e}")
