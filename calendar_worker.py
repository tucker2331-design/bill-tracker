import os
import json
import requests
import gspread
import pandas as pd
import re
import io
import tempfile
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from bs4 import BeautifulSoup
import pdfplumber

print("🚀 Waking up Enterprise Calendar Worker (State Machine + Smart Fiefdom Extractor)...")

# --- CONFIGURATION ---
SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# --- ENTERPRISE LEXICON ---
LOCAL_LEXICON = {
    "House Appropriations": ["appropriations"], "House Courts of Justice": ["courts of justice"],
    "House Rules": ["rules"], "House Finance": ["finance"],
    "House Counties, Cities and Towns": ["counties, cities and towns"],
    "House Privileges and Elections": ["privileges and elections"],
    "House Public Safety": ["public safety"],
    "House Communications, Technology and Innovation": ["communications", "technology"],
    "House Education": ["education"],
    "House Agriculture, Chesapeake and Natural Resources": ["agriculture", "natural resources"],
    "House General Laws": ["general laws"], "House Transportation": ["transportation"],
    "House Labor and Commerce": ["labor and commerce", "labor"],
    "House Health and Human Services": ["health and human services", "health"],
    "Senate Finance and Appropriations": ["finance and appropriations", "finance"],
    "Senate Courts of Justice": ["courts of justice"], "Senate Rules": ["rules"],
    "Senate Rehabilitation and Social Services": ["rehabilitation and social services", "rehabilitation"],
    "Senate Local Government": ["local government"],
    "Senate Privileges and Elections": ["privileges and elections"],
    "Senate Education and Health": ["education and health", "education", "health"],
    "Senate Commerce and Labor": ["commerce and labor", "commerce"],
    "Senate General Laws and Technology": ["general laws and technology", "general laws"],
    "Senate Transportation": ["transportation"],
    "Senate Agriculture, Conservation and Natural Resources": ["agriculture", "conservation", "natural resources"]
}

def get_active_session():
    now = datetime.now()
    year = now.year
    years_to_check = [year + 1, year] if now.month >= 11 else [year]
    for y in years_to_check:
        for suffix in ["10", "9", "8", "7", "6", "5", "4", "3", "2", "1"]:
            session_code = f"{y}{suffix}"
            test_url = f"https://lis.blob.core.windows.net/lisfiles/{session_code}/HISTORY.CSV"
            try:
                if requests.head(test_url, timeout=3).status_code == 200: return session_code
            except: pass
    return f"{year}1"

def safe_fetch_csv(url):
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            raw_text = res.content.decode('iso-8859-1')
            df = pd.read_csv(io.StringIO(raw_text))
            return df.rename(columns=lambda x: x.strip())
    except: pass
    return pd.DataFrame()

# --- THE SMART FIEFDOM EXTRACTION ENGINE ---
def extract_rogue_agenda(url, target_date_str=None, depth=0):
    """Downloads agendas, extracts bills, and smartly bypasses HTML landing pages by Date."""
    if depth > 1: return [] # Prevents infinite loops
    
    found_bills = set()
    regex_pattern = r'\b[HS][A-Za-z]{0,2}\s*\d+\b'
    if url.startswith('/'): url = f"https://lis.virginia.gov{url}"
        
    try:
        res = requests.get(url, timeout=15)
        if res.status_code != 200: return []
        
        # 1. If it's a PDF, extract the text
        if '.pdf' in url.lower() or b'%PDF' in res.content[:5]:
            print(f"📄 Extracting PDF: {url}")
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                temp_pdf.write(res.content)
                temp_pdf_path = temp_pdf.name
            with pdfplumber.open(temp_pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        matches = re.findall(regex_pattern, text)
                        found_bills.update([m.replace(" ", "").upper() for m in matches])
            os.remove(temp_pdf_path)
            
        # 2. If it's HTML, check for a "Wrapper" logically
        else:
            soup = BeautifulSoup(res.text, 'html.parser')
            target_href = None
            
            # SMART CLICK: If we have a target date, find the specific table row for it
            if target_date_str:
                date_alt = target_date_str.replace('/0', '/') # Handles 03/04 vs 3/4
                for row in soup.find_all(['tr', 'li', 'div']): 
                    row_text = row.get_text()
                    if target_date_str in row_text or date_alt in row_text:
                        link = row.find('a', string=re.compile(r'Agenda', re.I)) or row.find('a', href=re.compile(r'\.pdf$', re.I))
                        if link:
                            target_href = link.get('href')
                            break
            
            # Fallback if no specific date match found
            if not target_href:
                agenda_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.I))
                if not agenda_links:
                    agenda_links = soup.find_all('a', string=re.compile(r'Agenda', re.I))
                if agenda_links:
                    target_href = agenda_links[0].get('href')
                    
            if target_href:
                # Fix relative links from Senate Finance
                if target_href.startswith('/'):
                    base_url = "/".join(url.split("/")[:3]) 
                    target_href = base_url + target_href
                print(f"🔗 Smart Bypass Triggered for {target_date_str}! Hopping to: {target_href}")
                return extract_rogue_agenda(target_href, target_date_str, depth + 1)
            
            # If no wrapper links, just rip the raw HTML text
            text = soup.get_text(separator=' ')
            matches = re.findall(regex_pattern, text)
            found_bills.update([m.replace(" ", "").upper() for m in matches])
            
    except Exception as e:
        print(f"⚠️ Extraction Failed for {url}: {e}")
    return sorted(list(found_bills))

def run_calendar_update():
    print("🔐 Authenticating with Google Cloud...")
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json: 
        print("🚨 CRITICAL: No GCP Credentials found.")
        return
        
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    sheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sheet.worksheet("Sheet1")

    ACTIVE_SESSION = get_active_session()
    blob_code = f"20{ACTIVE_SESSION}" if len(ACTIVE_SESSION) == 3 else ACTIVE_SESSION

    master_events = []
    convene_times = {}
    api_schedule_map = {}
    docket_memory = {} 

    test_start_date = datetime(2026, 3, 4)
    test_end_date = datetime(2026, 3, 10)

    print("📡 Downloading DOCKET.CSV (Building Relational Cache)...")
    df_docket = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/DOCKET.CSV")
    if not df_docket.empty:
        df_docket.columns = df_docket.columns.str.strip().str.lower().str.replace(' ', '_')
        bill_col = next((c for c in df_docket.columns if 'bill' in c), None)
        date_col = next((c for c in df_docket.columns if 'date' in c), None)
        comm_col = next((c for c in df_docket.columns if 'comm' in c or 'des' in c), None)
        
        if bill_col and date_col and comm_col:
            for _, row in df_docket.iterrows():
                b_num = str(row[bill_col]).replace(" ", "").upper()
                m_date = pd.to_datetime(row[date_col], errors='coerce')
                c_name = str(row[comm_col]).strip()
                if pd.notna(m_date) and b_num and c_name and c_name.lower() != 'nan':
                    date_str = m_date.strftime('%Y-%m-%d')
                    if date_str not in docket_memory: docket_memory[date_str] = {}
                    docket_memory[date_str][b_num] = c_name

    print("📡 Downloading Live API Schedule & Hunting Agendas...")
    try:
        sched_res = requests.get("https://lis.virginia.gov/Schedule/api/getschedulelistasync", headers=HEADERS, params={"sessionCode": ACTIVE_SESSION}, timeout=10)
        if sched_res.status_code == 200:
            schedules = sched_res.json().get('Schedules', []) if isinstance(sched_res.json(), dict) else sched_res.json()
            for meeting in schedules:
                meeting_date = pd.to_datetime(meeting.get('ScheduleDate', '1970-01-01'), errors='coerce')
                if not (test_start_date <= meeting_date <= test_end_date): continue
                date_str = meeting_date.strftime('%Y-%m-%d')
                owner_name = str(meeting.get('OwnerName', '')).strip()
                is_cancelled = meeting.get('IsCancelled', False)
                status = "CANCELLED" if is_cancelled else ""
                
                raw_time = str(meeting.get('ScheduleTime', '')).strip()
                raw_desc = str(meeting.get('Description', ''))
                clean_desc = re.sub(r'<[^>]+>', '', raw_desc).strip()
                
                agenda_url = None
                link_match = re.search(r'href=[\'"]?([^\'" >]+)', raw_desc)
                if link_match and ("agenda" in raw_desc.lower() or "docket" in raw_desc.lower() or "info" in raw_desc.lower()):
                    agenda_url = link_match.group(1)
                
                time_val = raw_time
                dynamic_markers = ["upon adjournment", "minutes after", "to be determined", "tba", "recess"]
                if any(m in clean_desc.lower() for m in dynamic_markers):
                    for part in clean_desc.split(';'):
                        if any(m in part.lower() for m in dynamic_markers):
                            time_val = part.strip()
                            break
                if not time_val: time_val = "Time TBA"
                
                owner_lower = owner_name.lower()
                if "house convenes" in owner_lower or "house chamber" in owner_lower:
                    if date_str not in convene_times: convene_times[date_str] = {}
                    convene_times[date_str]["House"] = {"Time": time_val, "Name": owner_name}
                elif "senate convenes" in owner_lower or "senate chamber" in owner_lower:
                    if date_str not in convene_times: convene_times[date_str] = {}
                    convene_times[date_str]["Senate"] = {"Time": time_val, "Name": owner_name}
                
                map_key = f"{date_str}_{owner_name}"
                if map_key not in api_schedule_map: api_schedule_map[map_key] = {"Time": time_val, "Status": status}
                
                if any(k in owner_lower for k in ["caucus", "session", "floor", "convenes", "adjourned"]):
                    master_events.append({"Date": date_str, "Time": time_val, "Status": status, "Committee": owner_name if owner_name else "Chamber Event", "Bill": "📌 " + clean_desc, "Outcome": "", "AgendaOrder": -1, "Source": "API"})
                    continue
                
                # --- NEW PRIORITY LOGIC: REGEX > DOCKET ---
                has_docket = False
                combined_bills = set()
                
                # Step 1: Always check for a predictive Agenda Link first
                if agenda_url and not is_cancelled:
                    target_date_formatted = meeting_date.strftime('%m/%d/%Y') # Format for smart clicking
                    print(f"🕵️‍♂️ Scanning Predictive Agenda for {target_date_formatted}: {agenda_url}")
                    extracted_bills = extract_rogue_agenda(agenda_url, target_date_formatted)
                    combined_bills.update(extracted_bills)
                
                # Step 2: Merge with the central CSV backup
                if date_str in docket_memory:
                    for b_num, comm in docket_memory[date_str].items():
                        if comm.lower().strip() == owner_name.lower().strip():
                            combined_bills.add(b_num)
                            
                # Step 3: Map the combined priority bills to the UI
                if combined_bills:
                    for bill in sorted(list(combined_bills)):
                        master_events.append({"Date": date_str, "Time": time_val, "Status": status, "Committee": owner_name, "Bill": bill, "Outcome": "Scheduled", "AgendaOrder": 1, "Source": "DOCKET"})
                        # QUARANTINE: Do NOT overwrite docket_memory. Keeps CSV pure.
                    has_docket = True

                if not has_docket:
                    master_events.append({"Date": date_str, "Time": time_val, "Status": status, "Committee": owner_name, "Bill": "📌 No live docket", "Outcome": "", "AgendaOrder": -1, "Source": "API_Skeleton"})
                    
    except Exception as e: print(f"🚨 API Schedule failed: {e}")

    print("📡 Processing HISTORY.CSV via State Machine...")
    df_past = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
    if not df_past.empty:
        bill_col = next((c for c in df_past.columns if 'bill' in c.lower()), 'BillNumber')
        date_col = next((c for c in df_past.columns if 'date' in c.lower()), 'HistoryDate')
        desc_col = next((c for c in df_past.columns if 'desc' in c.lower() or 'action' in c.lower()), 'Description')
        df_past['CleanBill'] = df_past[bill_col].astype(str).str.replace(' ', '').str.upper()
        df_past['ParsedDate'] = pd.to_datetime(df_past[date_col], errors='coerce')
        df_past = df_past[(df_past['ParsedDate'] >= test_start_date) & (df_past['ParsedDate'] <= test_end_date)]
        pattern = '|'.join(['report', 'continue', 'pass', 'fail', 'incorporate', 'hearing', 'strike', 'stricken', 'veto', 'sign', 'agreed', 'read', 'refer', 'waive', 'recommend', 'receive', 'release', 'take', 'conferee', 'amendment', 'substitute'])
        df_past = df_past[df_past[desc_col].str.contains(pattern, case=False, na=False)]
        df_past = df_past.sort_values(by=['ParsedDate'])
        bill_locations = {}
        
        for _, row in df_past.iterrows():
            bill_num = row['CleanBill']
            outcome_text = str(row[desc_col]).strip()
            outcome_lower = outcome_text.lower()
            date_val = row['ParsedDate']
            date_str = date_val.strftime('%Y-%m-%d')
            
            if outcome_text.startswith('H '): acting_chamber, chamber_prefix = "House", "House "
            elif outcome_text.startswith('S '): acting_chamber, chamber_prefix = "Senate", "Senate "
            else: acting_chamber = "House" if bill_num.startswith('H') else "Senate"; chamber_prefix = f"{acting_chamber} "
            
            if bill_num not in bill_locations: bill_locations[bill_num] = chamber_prefix + "Floor"
            if not bill_locations[bill_num].startswith(chamber_prefix): bill_locations[bill_num] = chamber_prefix + "Floor"
            event_location = bill_locations[bill_num] 
            
            matched_committee = None
            for lex_key, aliases in LOCAL_LEXICON.items():
                if lex_key.startswith(chamber_prefix):
                    for alias in aliases:
                        if alias and alias in outcome_lower:
                            matched_committee = lex_key
                            break
                if matched_committee: break
                    
            committee_verbs = ["reported", "referred", "assigned", "continued", "passed by indefinitely", "recommend", "incorporate", "stricken", "placed on"]
            if matched_committee and any(v in outcome_lower for v in committee_verbs):
                event_location = matched_committee

            if "subcommittee recommends" in outcome_lower and not matched_committee:
                cached_comm = docket_memory.get(date_str, {}).get(bill_num)
                if cached_comm:
                    event_location = chamber_prefix + cached_comm if not cached_comm.startswith(chamber_prefix) else cached_comm
                else:
                    event_location = f"⚠️ [Unmapped Subcommittee] {chamber_prefix}Ledger"

            floor_reset_phrases = ["read first", "read second", "read third", "passed house", "passed senate", "agreed to", "rejected", "signed by", "presented", "received", "enrolled", "engrossed", "conferees:"]
            if any(p in outcome_lower for p in floor_reset_phrases):
                event_location = chamber_prefix + "Floor"

            if "referred to" in outcome_lower or "assigned to" in outcome_lower or "placed on" in outcome_lower:
                if matched_committee: bill_locations[bill_num] = matched_committee
            elif "reported from" in outcome_lower or "discharged from" in outcome_lower:
                bill_locations[bill_num] = chamber_prefix + "Floor"

            noise_words = ["impact statement", "substitute printed", "laid on speaker's table", "laid on clerk's desk", "presented", "reprinted", "engrossed by senate - committee substitute", "engrossed by house - committee substitute"]
            if any(n in outcome_lower for n in noise_words): continue
            
            time_val = "Ledger"
            status = ""
            api_key = f"{date_str}_{event_location}"
            if api_key in api_schedule_map:
                time_val = api_schedule_map[api_key]["Time"]
                status = api_schedule_map[api_key]["Status"]
            
            if event_location == "House Floor":
                anchor = convene_times.get(date_str, {}).get("House")
                if anchor: time_val, event_location = anchor["Time"], anchor["Name"]
            elif event_location == "Senate Floor":
                anchor = convene_times.get(date_str, {}).get("Senate")
                if anchor: time_val, event_location = anchor["Time"], anchor["Name"]
                
            master_events.append({"Date": date_str, "Time": time_val, "Status": status, "Committee": event_location, "Bill": bill_num, "Outcome": outcome_text, "AgendaOrder": 999, "Source": "CSV"})

    print("🧹 Cleaning Data...")
    final_df = pd.DataFrame(master_events)
    if not final_df.empty:
        final_df = final_df[~((final_df['Bill'] == "📌 No live docket") & final_df.duplicated(subset=['Date', 'Committee'], keep=False))]
        final_df = final_df.sort_values(by=['Date', 'Committee', 'Bill', 'Source'])
        final_df = final_df.drop_duplicates(subset=['Date', 'Committee', 'Bill'], keep='last')
        final_df = final_df.fillna("")
        sheet_data = [final_df.columns.values.tolist()] + final_df.values.tolist()
        print("💾 Writing to Enterprise Database...")
        worksheet.clear()
        worksheet.update(values=sheet_data, range_name="A1")
        print("✅ SUCCESS: Full Fusion Pipeline complete.")
    else:
        print("⚠️ No data generated for the window.")

if __name__ == "__main__": 
    run_calendar_update()
