import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime
import json

st.set_page_config(page_title="Logic Dry Run", layout="wide")
st.title("🧪 Step 3: Engine Logic Dry Run (HB1)")

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}
TARGET_URL = "https://lis.virginia.gov/Legislation/api/getlegislationsessionlistasync"

LIS_HISTORY_CSV = "https://lis.virginia.gov/cgi-bin/legp604.exe?261+oth+CSV+HISTORY"
LIS_DOCKET_CSV = "https://lis.virginia.gov/cgi-bin/legp604.exe?261+oth+CSV+DOCKET"

# --- V94 LOGIC PORTED FOR BACKEND ---
COMMITTEE_MAP = {
    "H01": "House Privileges and Elections", "H02": "House Courts of Justice", "H03": "House Education",
    "H04": "House General Laws", "H05": "House Roads and Internal Navigation", "H06": "House Finance",
    "H07": "House Appropriations", "H08": "House Counties, Cities and Towns", 
    "H10": "House Health, Welfare and Institutions", "H11": "House Conservation and Natural Resources",
    "H12": "House Agriculture", "H13": "House Militia, Police and Public Safety", 
    "H14": "House Labor and Commerce", "S03": "Senate Courts of Justice", "S05": "Senate Finance and Appropriations"
}

YOUTH_KEYWORDS = ["child", "youth", "juvenile", "minor", "student", "school", "parental", "infant", "baby", "child custody", "foster", "adoption", "delinquen"]
TOPIC_KEYWORDS = {
    "🗳️ Elections & Democracy": ["election", "vote", "ballot", "campaign", "poll", "voter", "registrar", "districting", "suffrage", "voting", "democracy"],
    "🏗️ Housing & Property": ["rent", "landlord", "tenant", "housing", "lease", "property", "zoning", "eviction", "homeowner", "residential", "condo", "building code"],
    "🏛️ Local Government": ["charter", "ordinance", "locality", "localities", "county", "counties", "city", "cities", "town", "annexation", "sovereign", "immunity", "municipal"],
    "✊ Labor & Workers Rights": ["wage", "salary", "worker", "employment", "labor", "union", "bargaining", "leave", "compensation", "workplace", "employee", "minimum", "overtime"],
    "💰 Economy & Business": ["tax", "commerce", "business", "market", "consumer", "corporation", "finance", "budget", "economic", "trade", "gaming", "casino", "abc", "alcohol"],
    "🎓 Education": ["school", "student", "education", "university", "college", "teacher", "curriculum", "scholarship", "tuition", "board of education", "higher education", "academic", "instruction", "learning", "literacy", "principal", "superintendent"],
    "🪖 Veterans & Military Affairs": ["veteran", "military", "armed forces", "national guard", "service member", "deployment", "civilian life", "defense"],
    "🚓 Public Safety": ["firearm", "gun", "police", "crime", "penalty", "enforcement", "prison", "arrest", "criminal", "weapon", "ammo", "magazine", "correctional", "facility", "incarcerat", "jail", "sheriff"],
    "⚖️ Criminal Justice & Courts": ["court", "judge", "attorney", "civil", "suit", "liability", "damages", "evidence", "jury", "appeal", "justice", "lawyer", "bar", "probation", "parole", "sentence", "sentencing", "custody", "divorce", "domestic", "violence", "abuse", "victim", "protective order"],
    "🏥 Health & Healthcare": ["health", "medical", "hospital", "patient", "doctor", "insurance", "care", "mental", "pharmacy", "drug", "medicaid", "nurse"],
    "🌳 Environment & Energy": ["energy", "water", "groundwater", "wastewater", "stormwater", "pollution", "environment", "climate", "solar", "conservation", "waste", "carbon", "natural resources", "wind", "power", "electricity", "hydroelectric", "nuclear", "chesapeake", "bay", "river", "watershed"],
    "🚗 Transportation": ["road", "highway", "vehicle", "driver", "license", "transit", "traffic", "transportation", "motor"],
    "💻 Tech & Utilities": ["internet", "broadband", "data", "privacy", "utility", "utilities", "cyber", "technology", "telecom", "artificial intelligence"],
    "⚖️ Civil Rights": ["discrimination", "rights", "equity", "minority", "minorities", "gender", "religious", "freedom", "speech"],
}

# --- THE MISSING FAILSAFE ---
def clean_bill_id(bill_text):
    if pd.isna(bill_text): return ""
    clean = str(bill_text).upper().replace(" ", "").strip()
    clean = re.sub(r'^([A-Z]+)0+(\d+)$', r'\1\2', clean)
    return clean

def clean_committee_name(name):
    if not name or str(name).lower() == 'nan': return ""
    name = str(name).strip()
    if name in COMMITTEE_MAP: return COMMITTEE_MAP[name]
    name = re.sub(r'\b(Simon|Rasoul|Willett|Helmer|Lucas|Surovell|Locke|Deeds|Favola|Marsden|Ebbin|McPike|Hayes|Carroll Foy)\b.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\(?Subcommittee:.*?\)?', '', name, flags=re.IGNORECASE)
    name = name.replace("Committee For", "").replace("Committee On", "").replace("Committee", "").strip()
    if name.startswith("H") and name[1].isupper() and not name.startswith("House"): name = "House " + name[1:]
    if name.startswith("S") and name[1].isupper() and not name.startswith("Senate"): name = "Senate " + name[1:]
    return name.title()

def get_smart_subject(title, comm):
    title_lower = str(title).lower()
    comm_lower = str(comm).lower()
    if "education" in comm_lower and "health" not in comm_lower: return "🎓 Education"
    if "finance" in comm_lower or "appropriations" in comm_lower: return "💰 Economy & Business"
    for cat, keys in TOPIC_KEYWORDS.items():
        for k in keys:
            pattern = r'\b' + re.escape(k) + r'(?:es|s)?\b'
            if re.search(pattern, title_lower, re.IGNORECASE): return cat
    return "📂 Unassigned / General"

def determine_lifecycle(status_text, committee_name, bill_id, history_text):
    status = str(status_text).lower()
    comm = str(committee_name).strip()
    hist = str(history_text).lower()
    
    if any(x in status for x in ["signed by governor", "enacted", "approved by governor", "chapter"]): return "✅ Signed & Enacted"
    if "vetoed" in status: return "❌ Vetoed"
    vip_keywords = ["enrolled", "communicated to governor", "bill text as passed senate and house", "bill text as passed house and senate"]
    if any(x in status for x in vip_keywords): return "✍️ Awaiting Signature"
    dead_keywords_status = ["tabled", "failed to report", "failed to pass", "passed by indefinitely", "left in", "defeated", "no action taken", "incorporated", "continued", "carry over", "pbi", "stricken"]
    if any(x in status for x in dead_keywords_status): return "❌ Dead / Tabled"
    floor_keywords = ["reported", "reading waived", "read second", "read third", "read first"]
    if any(x in status for x in floor_keywords):
        if "recommends reporting" not in status: return "📣 Out of Committee"
    if comm not in ["-", "nan", "None", "", "Unassigned"] and len(comm) > 2: return "📥 In Committee"
    if "referred to" in status and "governor" not in status: return "📥 In Committee"
    transit_keywords = ["passed", "agreed", "engrossed", "communicated", "received from"]
    if any(x in status for x in transit_keywords): return "📣 Out of Committee"
    return "📥 In Committee"

if st.button("🧪 Run HB1 Logic Test"):
    with st.spinner("Pulling data..."):
        # 1. Pull API (Master List)
        api_data = requests.get(TARGET_URL, headers=HEADERS, params={"sessionCode": "20261"}).json()
        bills_list = api_data.get("Legislations", [])
        hb1_data = next((b for b in bills_list if b.get("LegislationNumber") == "HB1"), None)
        
        # 2. Pull CSV Blobs
        hist_df = pd.read_csv(LIS_HISTORY_CSV, encoding='ISO-8859-1', on_bad_lines='skip')
        hist_df.columns = hist_df.columns.str.strip().str.lower().str.replace(' ', '_')
        hist_col = next((c for c in hist_df.columns if c in ['bill_number','bill_id','bill_no']), None)
        
        # Applying the clean_bill_id failsafe!
        if hist_col:
            hist_df['bill_clean'] = hist_df[hist_col].astype(str).apply(clean_bill_id)
            hb1_history = hist_df[hist_df['bill_clean'] == 'HB1'].to_dict('records')
        else:
            hb1_history = []

        doc_df = pd.read_csv(LIS_DOCKET_CSV, encoding='ISO-8859-1', on_bad_lines='skip')
        doc_df.columns = doc_df.columns.str.strip().str.lower().str.replace(' ', '_')
        doc_col = next((c for c in doc_df.columns if c in ['bill_number','bill_id','bill_no']), None)
        
        # Applying the clean_bill_id failsafe!
        if doc_col:
            doc_df['bill_clean'] = doc_df[doc_col].astype(str).apply(clean_bill_id)
            hb1_docket = doc_df[doc_df['bill_clean'] == 'HB1'].to_dict('records')
        else:
            hb1_docket = []

        # --- THE PROCESSING ENGINE ---
        bill_num = "HB1"
        title = hb1_data.get("Description", "No Title")
        raw_status = hb1_data.get("LegislationStatus", "Unknown")
        
        curr_comm = "-"; curr_sub = "-"; history_data = []; history_blob = ""; date_val = ""
        
        # Parse History
        for h_row in hb1_history:
            desc = ""; date_h = ""
            for col in ['history_description', 'description', 'action', 'history']:
                if col in h_row and pd.notna(h_row[col]): desc = str(h_row[col]); break
            for col in ['history_date', 'date', 'action_date']:
                if col in h_row and pd.notna(h_row[col]): date_h = str(h_row[col]); break

            if desc:
                history_data.append({"Date": date_h, "Action": desc})
                history_blob += desc.lower() + " "
                date_val = date_h 
                
                # Anchor Logic
                if any(x in desc.lower() for x in ["referred to"]):
                    match = re.search(r'referred to\s?([a-z\s&,-]+)', desc.lower())
                    if match: curr_comm = "House " + match.group(1).strip().title()
                if "sub:" in desc.lower():
                    try: curr_sub = desc.lower().split("sub:")[1].strip().title()
                    except: pass
                if "reported" in desc.lower() or "passed house" in desc.lower():
                    if "recommends" not in desc.lower() and "failed" not in desc.lower():
                        curr_comm = "Unassigned"; curr_sub = "-"

        curr_comm = clean_committee_name(curr_comm)
        lifecycle = determine_lifecycle(raw_status, curr_comm, bill_num, history_blob)
        auto_folder = get_smart_subject(title, curr_comm)
        is_youth = any(k in title.lower() for k in YOUTH_KEYWORDS)
        
        display_comm = curr_comm
        if "Out of Committee" in lifecycle or "Passed" in lifecycle or "Signed" in lifecycle or "Awaiting" in lifecycle:
            display_comm = "📜 On Floor / Chamber Action"

        # Construct Final Payload
        final_payload = {
            "Bill Number": bill_num,
            "Official Title": title,
            "Status": raw_status,
            "Date": date_val,
            "Lifecycle": lifecycle,
            "Auto_Folder": auto_folder,
            "Is_Youth": is_youth,
            "Current_Committee": curr_comm,
            "Display_Committee": display_comm,
            "Current_Sub": curr_sub,
            "History_Data": json.dumps(history_data),
            "Upcoming_Meetings": json.dumps([]) 
        }

        st.success("✅ Engine Processing Complete!")
        st.json(final_payload)
