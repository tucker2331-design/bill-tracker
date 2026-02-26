import streamlit as st
import requests
import re

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
SESSION_CODE = "20261"
URL = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"

st.set_page_config(page_title="LIS API Debugger v2", layout="wide")
st.title("🛠️ LIS API Raw Data Debugger (Unfiltered)")

@st.cache_data(ttl=60)
def fetch_debug_data():
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    raw_data = []
    
    # We must NOT use startDate/endDate because it breaks the API
    for chamber in ["H", "S"]:
        params = {
            "sessionCode": SESSION_CODE, 
            "chamberCode": chamber 
        }
        try:
            resp = requests.get(URL, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("Schedules", data.get("ListItems", []))
                for item in items:
                    item["_Chamber"] = "House" if chamber == "H" else "Senate"
                    raw_data.append(item)
        except Exception as e:
            st.error(f"Error fetching {chamber}: {e}")
                
    return raw_data

with st.spinner("Pulling massive unfiltered database records..."):
    raw_items = fetch_debug_data()

if not raw_items:
    st.error("No data returned from the API.")
else:
    debug_list = []
    for item in raw_items:
        desc = str(item.get("Description", ""))
        comm = str(item.get("Comments", ""))
        
        # 1. Hunt for standard HTML href links
        html_links = re.findall(r'href=[\'"]?([^\'" >]+)', desc + " " + comm)
        
        # 2. Hunt for raw text URLs (http://...)
        raw_urls = re.findall(r'(https?://[^\s]+)', desc + " " + comm)
        
        # 3. Hunt for legacy Javascript links
        js_links = re.findall(r'window\.open\([\'"]([^\'"]+)[\'"]\)', desc + " " + comm)
        
        # Combine and deduplicate all found links
        all_found_links = list(set(html_links + raw_urls + js_links))

        debug_list.append({
            "Date": item.get("ScheduleDate", "").split("T")[0],
            "Chamber": item.get("_Chamber"),
            "Committee": item.get("OwnerName"),
            "Native_LinkURL": item.get("LinkURL"),
            "All_Links_Found": all_found_links,
            "Raw_Description": desc,
            "Raw_Comments": comm
        })

    # Render as an interactive dataframe
    st.dataframe(debug_list, use_container_width=True, height=600)
