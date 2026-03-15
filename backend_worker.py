import os
import json
import requests
import gspread
import pandas as pd
import re
import difflib
from datetime import datetime
from google.oauth2.service_account import Credentials

print("🚀 Waking up Ghost Worker...")

# --- CONFIGURATION ---
SPREADSHEET_ID = "1566pCv70iQ7YkTQK71RfYerciK-ukW-QdblTu2-Prfw"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

def get_active_session():
    now = datetime.now()
    year = now.year
    years_to_check = [year + 1, year] if now.month >= 11 else [year]
    for y in years_to_check:
        for suffix in ["10", "9", "8", "7", "6", "5", "4", "3", "2", "1"]:
            session_code = f"{y}{suffix}"
            test_url = f"https://lis.blob.core.windows.net/lisfiles/{session_code}/HISTORY.CSV"
            try:
                if requests.head(test_url, timeout=3).status_code == 200:
                    return session_code
            except: pass
    return f"{year}1"

ACTIVE_SESSION = get_active_session()
TARGET_URL = "https://lis.virginia.gov/Legislation/api/getlegislationsessionlistasync"
LIS_HISTORY_CSV = f"https://lis.blob.core.windows.net/lisfiles/{ACTIVE_SESSION}/HISTORY.CSV"
LIS_DOCKET_CSV = f"https://lis.blob.core.windows.net/lisfiles/{ACTIVE_SESSION}/DOCKET.CSV"

COMMITTEE_MAP = {
    "H01": "House Privileges and Elections", "H02": "House Courts of Justice", "H03": "House Education",
    "H04": "House General Laws", "H05": "House Roads and Internal Navigation", "H06": "House Finance",
    "H07": "House Appropriations", "H08": "House Counties, Cities and Towns", 
    "H10": "House Health, Welfare and Institutions", "H11": "House Conservation and Natural Resources",
    "H12": "House Agriculture", "H13": "House Militia, Police and Public Safety", 
    "H14": "House Labor and Commerce", "S01": "Senate Agriculture", "S02": "Senate Commerce and Labor", 
    "S03": "Senate Courts of Justice", "S04": "Senate Education and Health", "S05": "Senate Finance and Appropriations", 
    "S06": "Senate General Laws", "S07": "Senate Local Government", "S08": "Senate Privileges and Elections", 
    "S09": "Senate Rehab", "S10": "Senate Transportation", "S11": "Senate Rules"
}

YOUTH_KEYWORDS = ["child", "youth", "juvenile", "minor", "student", "school", "parental", "infant", "baby", "child custody", "foster", "adoption", "delinquen"]
TOPIC_KEYWORDS = {
    "🎖️ Commendations & Memorials": ["commend", "celebrat", "memorial", "confirming appointments", "congratulat", "recognizing", "honoring", "in memory of"],
    "🗳️ Elections & Democracy": ["election", "vote", "ballot", "campaign finance", "poll", "voter", "registrar", "districting", "suffrage", "voting", "democracy", "electoral board", "department of elections", "absentee"],
    "🏗️ Housing & Property": ["rent", "landlord", "tenant", "housing", "lease", "property", "zoning", "eviction", "homeowner", "residential", "condo", "building code", "real estate", "foreclosure", "short-term rental", "uniform statewide building code"],
    "🏛️ Local Government": ["charter", "ordinance", "locality", "localities", "county", "counties", "city", "cities", "town", "annexation", "sovereign immunity", "municipal", "board of supervisors", "city council", "comprehensive plan", "planning commission"],
    "✊ Labor & Workers Rights": ["wage", "salary", "worker", "employment", "labor", "union", "collective bargaining", "leave", "compensation", "workplace", "employee", "overtime", "occupational safety", "workers' compensation", "prevailing wage", "apprenticeship"],
    "💰 Economy & Business": ["tax", "commerce", "business", "consumer", "corporation", "finance", "budget", "economic", "trade", "gaming", "casino", "alcoholic beverage control", "retail franchise", "sales and use tax", "income tax", "procurement", "cryptocurrency"],
    "🎓 Education": ["school", "student", "education", "university", "college", "teacher", "curriculum", "scholarship", "tuition", "board of education", "higher education", "academic", "instruction", "learning", "literacy", "principal", "superintendent", "sol assessment", "campus", "historically black colleges"],
    "🪖 Veterans & Military Affairs": ["veteran", "military", "armed forces", "national guard", "service member", "deployment", "civilian life", "department of veterans services", "military spouse", "active duty"],
    "🚓 Public Safety": ["police", "crime", "penalty", "enforcement", "prison", "arrest", "criminal", "ammo", "magazine", "correctional", "incarcerat", "jail", "sheriff", "handgun", "assault", "felony", "misdemeanor", "law-enforcement officer", "state police", "fire department", "emergency management", "fentanyl"],
    "⚖️ Criminal Justice & Courts": ["court", "judge", "attorney", "civil action", "suit", "liability", "damages", "evidence", "jury", "appeal", "justice", "lawyer", "probation", "parole", "sentencing", "custody", "divorce", "domestic violence", "protective order", "magistrate", "supreme court of virginia", "juvenile and domestic relations"],
    "🏥 Health & Healthcare": ["health", "medical", "hospital", "patient", "doctor", "insurance", "mental health", "pharmacy", "drug", "medicaid", "nurse", "physician", "prescription", "department of health", "board of medicine", "behavioral health", "maternal", "reproductive", "telemedicine", "dental"],
    "🌳 Environment & Energy": ["energy", "water", "groundwater", "wastewater", "stormwater", "pollution", "environment", "climate", "solar", "conservation", "waste", "carbon", "natural resources", "wind", "electricity", "hydroelectric", "nuclear", "chesapeake bay", "watershed", "department of environmental quality", "recycling", "renewable"],
    "🚗 Transportation": ["road", "highway", "vehicle", "driver", "license", "transit", "traffic", "transportation", "motor", "speed monitoring", "department of motor vehicles", "toll", "bridge", "intersection", "pedestrian", "crosswalk", "aviation", "airport"],
    "💻 Tech & Utilities": ["internet", "broadband", "data", "privacy", "utility", "utilities", "cyber", "technology", "telecom", "artificial intelligence", "state corporation commission", "broadband authority", "algorithm", "biometric"],
    "⚖️ Civil Rights": ["discrimination", "rights", "equity", "minority", "minorities", "gender", "religious freedom", "speech", "hate crime", "human rights", "equal pay", "diversity"],
}

def clean_bill_id(bill_text):
    if pd.isna(bill_text): return ""
    clean = str(bill_text).upper().replace(" ", "").strip()
    return re.sub(r'^([A-Z]+)0+(\d+)$', r'\1\2', clean)

def clean_committee_name(name):
    if not name or str(name).lower() == 'nan': return "Unassigned"
    name = str(name).strip()
    if name in COMMITTEE_MAP: return COMMITTEE_MAP[name]
    clean_name = name.replace("Committee For", "").replace("Committee On", "").replace("Committee", "").strip()
    if clean_name.startswith("H") and clean_name[1].isupper() and not clean_name.startswith("House"): clean_name = "House " + clean_name[1:]
    if clean_name.startswith("S") and clean_name[1].isupper() and not clean_name.startswith("Senate"): clean_name = "Senate " + clean_name[1:]
    clean_name = clean_name.title()

    best_match, highest_ratio = None, 0.0
    for valid_comm in COMMITTEE_MAP.values():
        ratio = difflib.SequenceMatcher(None, clean_name.lower(), valid_comm.lower()).ratio()
        if ratio > highest_ratio: highest_ratio, best_match = ratio, valid_comm
    if highest_ratio >= 0.95: return best_match
    return clean_name

def get_smart_subject(title, comm, bill_id):
    title_lower, comm_lower, b_id_upper = str(title).lower(), str(comm).lower(), str(bill_id).upper()
    
    # The Soundproof Room: Safe Ceremonial Catch
    if any(b_id_upper.startswith(prefix) for prefix in ["HJ", "HR", "SJ", "SR"]):
        if any(x in title_lower for x in ["commend", "celebrat", "memorial", "confirming appointments"]):
            return "🎖️ Commendations & Memorials"

    if "education" in comm_lower and "health" not in comm_lower: return "🎓 Education"
    if "finance" in comm_lower or "appropriations" in comm_lower: return "💰 Economy & Business"
    
    for cat, keys in TOPIC_KEYWORDS.items():
        for k in keys:
            if re.search(r'\b' + re.escape(k) + r'(?:es|s)?\b', title_lower, re.IGNORECASE): return cat
            
    return "📂 Unassigned / General"

def determine_lifecycle(status_text, committee_name, bill_id, history_text):
    status, comm = str(status_text).lower(), str(committee_name).strip()
    
    if any(x in status for x in ["signed by governor", "enacted", "approved", "chapter"]): return "✅ Signed & Enacted"
    if "vetoed" in status: return "❌ Vetoed"
    if any(x in status for x in ["pending governor", "awaiting governor", "awaiting signature", "enrolled", "communicated to governor", "bill text as passed"]): return "✍️ Awaiting Signature"
    if any(x in status for x in ["tabled", "failed", "passed by indefinitely", "left in", "defeated", "no action taken", "incorporated", "continued", "carry over", "pbi", "stricken", "withdrawn"]): return "❌ Dead / Tabled"
    if any(x in status for x in ["reported", "reading waived", "read second", "read third", "read first"]) and "recommends reporting" not in status: return "📣 Out of Committee"
    
    if "introduced" in status and comm in ["-", "nan", "None", "", "Unassigned"]: return "📥 Awaiting Referral"
    
    if comm not in ["-", "nan", "None", "", "Unassigned"] and len(comm) > 2: return "📥 In Committee"
    if any(x in status for x in ["referred to", "in committee", "prefiled", "recommitted"]) and "governor" not in status: return "📥 In Committee"
    if any(x in status for x in ["passed", "agreed", "engrossed", "communicated", "received from", "in conference", "in senate", "in house"]): return "📣 Out of Committee"
    
    return "📣 Out of Committee (⚠️ Unrecognized)"

def run_update():
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json: return
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    sheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet, bug_worksheet = sheet.worksheet("Sheet1"), sheet.worksheet("Bug_Logs")

    api_data = requests.get(TARGET_URL, headers=HEADERS, params={"sessionCode": ACTIVE_SESSION}).json()
    bills_list = api_data.get("Legislations", [])
    
    hist_df = pd.read_csv(LIS_HISTORY_CSV, encoding='ISO-8859-1', on_bad_lines='skip')
    hist_df.columns = hist_df.columns.str.strip().str.lower().str.replace(' ', '_')
    hist_col = next((c for c in hist_df.columns if c in ['bill_number','bill_id','bill_no']), None)
    history_lookup = {b_id: group.to_dict('records') for b_id, group in hist_df.assign(bill_clean=hist_df[hist_col].astype(str).apply(clean_bill_id)).groupby('bill_clean')} if hist_col else {}

    doc_df = pd.read_csv(LIS_DOCKET_CSV, encoding='ISO-8859-1', on_bad_lines='skip')
    doc_df.columns = doc_df.columns.str.strip().str.lower().str.replace(' ', '_')
    doc_col = next((c for c in doc_df.columns if c in ['bill_number','bill_id','bill_no']), None)
    docket_lookup = {b_id: group.to_dict('records') for b_id, group in doc_df.assign(bill_clean=doc_df[doc_col].astype(str).apply(clean_bill_id)).groupby('bill_clean')} if doc_col else {}

    sheet_data = [["Bill Number", "Official Title", "Status", "Date", "Lifecycle", "Auto_Folder", "Is_Youth", "Current_Committee", "Display_Committee", "Current_Sub", "Latest_Vote", "History_Data", "Upcoming_Meetings"]]
    existing_logs = bug_worksheet.get_all_records()
    df_logs = pd.DataFrame(existing_logs) if existing_logs else pd.DataFrame(columns=["Date_Found", "Bill_Number", "Bug_Type", "Details", "Status"])
    for col in ["Date_Found", "Bill_Number", "Bug_Type", "Details", "Status"]:
        if col not in df_logs.columns: df_logs[col] = ""
    new_bugs_to_log = []
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    for item in bills_list:
        bill_num, title, raw_status = item.get("LegislationNumber", "Unknown"), item.get("Description", "No Title"), item.get("LegislationStatus", "Unknown")
        curr_comm, curr_sub, latest_vote, history_data, history_blob, date_val = "Unassigned", "-", "-", [], "", ""
        
        for h_row in history_lookup.get(bill_num, []):
            desc = next((str(h_row[c]) for c in ['history_description', 'description', 'action', 'history'] if c in h_row and pd.notna(h_row[c])), "")
            date_h = next((str(h_row[c]) for c in ['history_date', 'date', 'action_date'] if c in h_row and pd.notna(h_row[c])), "")

            if desc:
                history_data.append({"Date": date_h, "Action": desc})
                history_blob += desc.lower() + " "; date_val = date_h 
                sub_match = re.search(r'(Subcommittee[^)]*)', desc, re.IGNORECASE)
                if sub_match: curr_sub = sub_match.group(1).strip()
                vote_match = re.search(r'\(\s*(\d+-Y\s+\d+-N.*?)\s*\)', desc, re.IGNORECASE)
                if vote_match: latest_vote = vote_match.group(1).strip()
                if "referred to" in desc.lower():
                    match = re.search(r'referred to\s?([a-z\s&,-]+)', desc.lower())
                    if match: curr_comm = "House " + match.group(1).split('(')[0].strip().title() if desc.startswith("H ") else "Senate " + match.group(1).split('(')[0].strip().title()
                if any(x in desc.lower() for x in ["reported", "passed house", "passed senate"]) and "recommends" not in desc.lower() and "failed" not in desc.lower():
                    curr_comm, curr_sub = "Unassigned", "-"

        curr_comm = clean_committee_name(curr_comm)
        lifecycle = determine_lifecycle(raw_status, curr_comm, bill_num, history_blob)
        auto_folder = get_smart_subject(title, curr_comm, bill_num)
        
        display_comm = "📜 On Floor / Chamber Action" if any(x in lifecycle for x in ["Out of Committee", "Passed", "Signed", "Awaiting"]) else curr_comm
            
        upcoming_meetings = []
        for d in docket_lookup.get(bill_num, []):
            d_date = next((str(d[c]) for c in ['meeting_date', 'doc_date', 'date'] if c in d and pd.notna(d[c])), "")
            d_comm_raw = next((str(d[c]) for c in ['committee_name', 'com_des'] if c in d and pd.notna(d[c])), "")
            if d_date: upcoming_meetings.append({"Date": d_date, "CommitteeRaw": d_comm_raw})

        if "⚠️ Unrecognized" in lifecycle and df_logs[(df_logs['Bill_Number'].astype(str) == bill_num) & (df_logs['Bug_Type'] == "🚨 Unrecognized Status Phrase")].empty:
            new_bugs_to_log.append([today_str, bill_num, "🚨 Unrecognized Status Phrase", raw_status, "🚨 Open"])
        
        if lifecycle == "📥 In Committee" and display_comm == "Unassigned" and df_logs[(df_logs['Bill_Number'].astype(str) == bill_num) & (df_logs['Bug_Type'] == "🧭 Unmapped Committee Name")].empty:
            new_bugs_to_log.append([today_str, bill_num, "🧭 Unmapped Committee Name", raw_status, "🚨 Open"])
        
        if auto_folder == "📂 Unassigned / General" and df_logs[(df_logs['Bill_Number'].astype(str) == bill_num) & (df_logs['Bug_Type'] == "🗂️ Missing Topic Keyword")].empty:
            new_bugs_to_log.append([today_str, bill_num, "🗂️ Missing Topic Keyword", title, "🚨 Open"])

        sheet_data.append([bill_num, title, raw_status, date_val, lifecycle, auto_folder, str(any(k in title.lower() for k in YOUTH_KEYWORDS)), curr_comm, display_comm, curr_sub, latest_vote, json.dumps(history_data), json.dumps(upcoming_meetings)])

    worksheet.clear()
    worksheet.update(values=sheet_data, range_name="A1")
    if new_bugs_to_log: bug_worksheet.append_rows(new_bugs_to_log)

if __name__ == "__main__": run_update()
