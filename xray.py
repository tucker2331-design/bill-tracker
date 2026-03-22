import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="Architecture Sandbox", layout="wide")
st.title("🧪 Enterprise Architecture Sandbox")

# --- TEST 1: TIME PARSER ---
st.header("Test 1: 24-Hour Time Enforcer")

def test_time_parser(raw_time, parent_time_24h=None):
    time_val = raw_time.strip().replace('.', '').upper()
    
    # 1. Handle Adjournment Math
    if any(m in time_val.lower() for m in ["after", "upon"]):
        if parent_time_24h:
            try:
                pt = datetime.strptime(parent_time_24h, '%H:%M')
                pt = pt + timedelta(minutes=1)
                return pt.strftime('%H:%M')
            except: 
                return "06:00" # Fallback
        return "06:00" # Fallback
        
    # 2. Handle standard AM/PM parsing into 24-hour time
    try:
        parsed = datetime.strptime(time_val, '%I:%M %p')
        return parsed.strftime('%H:%M')
    except:
        pass
        
    return "23:59" # TBA Fallback

col1, col2 = st.columns(2)
with col1:
    st.write("**Inputs (What the API gives us):**")
    st.write("1. `9:30 a.m.`")
    st.write("2. `2:00 p.m.`")
    st.write("3. `15 minutes after adjournment` (Parent: 14:00)")
    st.write("4. `Upon adjournment` (No Parent)")
    st.write("5. `Time TBA`")

with col2:
    st.write("**Outputs (Strict 24H SortTime):**")
    st.code(f"""
1. {test_time_parser("9:30 a.m.")}
2. {test_time_parser("2:00 p.m.")}
3. {test_time_parser("15 minutes after adjournment", "14:00")}
4. {test_time_parser("Upon adjournment", None)}
5. {test_time_parser("Time TBA")}
    """)


# --- TEST 2: HOUSE JS BYPASS ---
st.header("Test 2: House JavaScript Bypass")
target_url = "https://house.vga.virginia.gov/subcommittees/H24001/agendas/5606"
st.write(f"**Targeting:** `{target_url}`")

def test_house_js_bypass(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return st.error(f"Failed to connect. Status: {res.status_code}")
            
        soup = BeautifulSoup(res.text, 'html.parser')
        script_tags = soup.find_all('script')
        found_bills = set()
        
        # Hunt in the JS scripts
        for script in script_tags:
            if script.string and ('{"' in script.string or 'SB' in script.string or 'HB' in script.string):
                matches = re.findall(r'\b([HS][A-Za-z]{0,2}\s*\d+)', script.string)
                found_bills.update([m.replace(" ", "").upper() for m in matches])
                
        # Hunt in the raw HTML text fallback
        text = soup.get_text(separator=' ')
        matches = re.findall(r'\b([HS][A-Za-z]{0,2}\s*\d+)', text)
        found_bills.update([m.replace(" ", "").upper() for m in matches])
        
        extracted_list = sorted(list(found_bills))
        st.write(f"**Bills Extracted:** {extracted_list}")
        
        if "SB53" in extracted_list:
            st.success("✅ SUCCESS: Bypassed JS and found the target bills.")
        elif len(extracted_list) > 0:
            st.warning("⚠️ PARTIAL: Found some bills, but missed SB53.")
        else:
            st.error("❌ FAILED: Found 0 bills. The data is locked behind a strict JSON API endpoint.")
            
    except Exception as e:
        st.error(f"Crash: {e}")

test_house_js_bypass(target_url)
