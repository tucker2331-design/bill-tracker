import os
import sys
import json
import time
import requests
import gspread
import pandas as pd
import re
import io
import tempfile
import urllib.parse
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from google.oauth2.service_account import Credentials
from bs4 import BeautifulSoup
import pdfplumber

print("🚀 Waking up Enterprise Calendar Worker (Session-Aware Master Build)...")

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

LOCAL_LEXICON = {
    "House Appropriations": ["appropriations"],
    "House Courts of Justice": ["courts of justice"],
    "House Rules": ["rules"], 
    "House Finance": ["finance"],
    "House Counties, Cities and Towns": ["counties, cities and towns"],
    "House Privileges and Elections": ["privileges and elections"],
    "House Public Safety": ["public safety"],
    "House Communications, Technology and Innovation": ["communications", "technology", "innovation"],
    "House Education": ["education"],
    "House Agriculture, Chesapeake and Natural Resources": ["agriculture", "natural resources"],
    "House General Laws": ["general laws"], 
    "House Transportation": ["transportation"],
    "House Labor and Commerce": ["labor and commerce", "labor"],
    "House Health and Human Services": ["health and human services", "health"],
    "Senate Finance and Appropriations": ["finance and appropriations", "finance"],
    "Senate Courts of Justice": ["courts of justice"], 
    "Senate Rules": ["rules"],
    "Senate Rehabilitation and Social Services": ["rehabilitation and social services", "rehabilitation"],
    "Senate Local Government": ["local government"],
    "Senate Privileges and Elections": ["privileges and elections"],
    "Senate Education and Health": ["education and health", "education", "health"],
    "Senate Commerce and Labor": ["commerce and labor", "commerce"],
    "Senate General Laws and Technology": ["general laws and technology", "general laws"],
    "Senate Transportation": ["transportation"],
    "Senate Agriculture, Conservation and Natural Resources": ["agriculture", "conservation", "natural resources"]
}

def get_armored_session():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'})
    retries = Retry(total=4, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# --- TARGET LOCKED: TRUE JSON SCHEMA APPLIED ---
def get_active_session_info(http_session):
    print("📡 Pinging Master API for Session Intelligence...")
    try:
        res = http_session.get("https://lis.virginia.gov/Session/api/GetSessionListAsync", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            raw_json = res.json()
            sessions = raw_json.get('Sessions', []) if isinstance(raw_json, dict) else raw_json
            
            if not isinstance(sessions, list) or len(sessions) == 0:
                print("🚨 API returned empty or malformed session list.")
                return None

            now = datetime.now()
            
            # Extracts absolute bounds from the nested SessionEvents array
            def extract_dates(session_obj):
                events = session_obj.get('SessionEvents', [])
                valid_dates = []
                for e in events:
                    d = e.get('ActualDate') or e.get('ProjectedDate')
                    if d:
                        try:
                            valid_dates.append(pd.to_datetime(d).replace(tzinfo=None))
                        except: pass
                if valid_dates:
                    return min(valid_dates), max(valid_dates)
                return now, now 

            # Pass 1: Explicit 'IsActive' Flag (Confirmed via JSON)
            for s in sessions:
                if s.get('IsActive') or s.get('IsDefault'):
                    start, end = extract_dates(s)
                    code = str(s.get('SessionCode'))
                    print(f"🎯 Target Locked: Session {code} ({start.strftime('%b %d')} - {end.strftime('%b %d')})")
                    return {"code": code, "start": start, "end": end + timedelta(days=14)}

            # Pass 2: Fallback to Current Year
            current_year = now.year
            for s in sessions:
                if str(s.get('SessionYear')) == str(current_year):
                    start, end = extract_dates(s)
                    code = str(s.get('SessionCode'))
                    print(f"🎯 Target Locked via Year Match: Session {code}")
                    return {"code": code, "start": start, "end": end + timedelta(days=14)}
                    
    except Exception as e:
        print(f"🚨 Master API Ping Failed: {e}")
    return None

def safe_fetch_csv(url):
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            raw_text = res.content.decode('iso-8859-1')
            df = pd.read_csv(io.StringIO(raw_text))
            return df.rename(columns=lambda x: x.strip())
    except: pass
    return pd.DataFrame()

def generate_date_variants(dt):
    m = str(dt.month); d = str(dt.day); y = str(dt.year)
    m_pad = f"{dt.month:02d}"; d_pad = f"{dt.day:02d}"; y_short = y[-2:]
    month_full = dt.strftime('%B'); month_short = dt.strftime('%b')
    return [
        f"{m_pad}/{d_pad}/{y}", f"{m}/{d}/{y}", f"{m_pad}/{d_pad}/{y_short}", f"{m}/{d}/{y_short}",
        f"{month_full} {d}", f"{month_short} {d}", f"{month_full} {d_pad}", f"{month_short} {d_pad}"
    ]

def parse_24h_time(raw_time, parent_time_24h=None):
    time_val = raw_time.strip().replace('.', '').upper()
    if any(m in time_val.lower() for m in ["after", "upon"]):
        if parent_time_24h and parent_time_24h != "06:00":
            try:
                pt = datetime.strptime(parent_time_24h, '%H:%M')
                pt = pt + timedelta(minutes=1)
                return pt.strftime('%H:%M')
            except: return "06:00" 
        return "06:00" 
    try:
        parsed = datetime.strptime(time_val, '%I:%M %p')
        return parsed.strftime('%H:%M')
    except: pass
    return "23:59"

def build_time_graph(schedules):
    raw_times = {}
    for m in schedules:
        name = str(m.get('OwnerName', '')).strip().lower()
        t_val = str(m.get('ScheduleTime', '')).strip()
        desc = re.sub(r'<[^>]+>', '', str(m.get('Description', ''))).strip()
        stitched = f"{t_val} {desc}".lower()
        raw_times[name] = t_val if not any(x in stitched for x in ["upon adjournment", "minutes after", "hour after", "recess"]) else stitched

    floor_keys = {}
    for k, v in raw_times.items():
        if "house convenes" in k or "house chamber" in k:
            floor_keys["house"] = v; floor_keys["the house"] = v
        if "senate convenes" in k or "senate chamber" in k:
            floor_keys["senate"] = v; floor_keys["the senate"] = v
    raw_times.update(floor_keys)

    resolved_times = {}
    
    def resolve_node(name_key, visited=None):
        if visited is None: visited = set()
        if name_key in resolved_times: return resolved_times[name_key]
        if name_key in visited: return "06:00" 
        
        visited.add(name_key)
        raw_str = raw_times.get(name_key, "")
        if not raw_str: return "23:59"

        dynamic_markers = ["upon adjournment", "minutes after", "hour after", "recess"]
        if any(m in raw_str.lower() for m in dynamic_markers):
            found_parent_key = None
            
            for p_name in raw_times.keys():
                if len(p_name) > 5 and p_name in raw_str.lower():
                    found_parent_key = p_name
                    break
            
            if not found_parent_key:
                raw_lower = raw_str.lower()
                if "senate adjourns" in raw_lower or "adjournment of the senate" in raw_lower:
                    found_parent_key = "senate convenes"
                elif "house adjourns" in raw_lower or "adjournment of the house" in raw_lower:
                    found_parent_key = "house convenes"
                elif "recess" in raw_lower and "house" in raw_lower:
                    for k, v in raw_times.items():
                        if "recess" in v.lower() and "house" in k.lower(): found_parent_key = k; break
                elif "recess" in raw_lower and "senate" in raw_lower:
                    for k, v in raw_times.items():
                        if "recess" in v.lower() and "senate" in k.lower(): found_parent_key = k; break

            if found_parent_key:
                parent_24h = resolve_node(found_parent_key, visited)
                res = parse_24h_time(raw_str, parent_24h)
                resolved_times[name_key] = res
                return res
            return "06:00"

        res = parse_24h_time(raw_str)
        resolved_times[name_key] = res
        return res

    for name in raw_times.keys(): resolve_node(name)
    return resolved_times

def extract_rogue_agenda(url, session, target_date_dt=None, depth=0):
    if depth > 1: return [], False 
    found_bills = set()
    regex_pattern = r'\b([HS][BJR]\s*\d+)'
    if url.startswith('/'): url = f"https://lis.virginia.gov{url}"
        
    try:
        time.sleep(0.25)
        res = session.get(url, timeout=15)
        if res.status_code != 200: return [], False
        
        if '.pdf' in url.lower() or b'%PDF' in res.content[:5]:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                    temp_pdf.write(res.content)
                    temp_pdf_path = temp_pdf.name
                with pdfplumber.open(temp_pdf_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            matches = re.findall(regex_pattern, text.replace(" ", ""))
                            found_bills.update([m.upper() for m in matches])
                os.remove(temp_pdf_path)
            except Exception: return [], True
        else:
            soup = BeautifulSoup(res.text, 'html.parser')
            target_href = None
            if target_date_dt:
                date_matrix = generate_date_variants(target_date_dt)
                for row in soup.find_all(['tr', 'li', 'div', 'p']): 
                    row_text = row.get_text()
                    if any(variant in row_text for variant in date_matrix):
                        link = row.find('a', string=re.compile(r'Agenda|Docket', re.I)) or row.find('a', href=re.compile(r'\.pdf$', re.I))
                        if link: target_href = link.get('href'); break
            if not target_href:
                agenda_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.I)) or soup.find_all('a', string=re.compile(r'Agenda|Docket', re.I))
                if agenda_links: target_href = agenda_links[0].get('href')
                    
            if target_href:
                absolute_url = urllib.parse.urljoin(url, target_href)
                return extract_rogue_agenda(absolute_url, session, target_date_dt, depth + 1)
            
            for script in soup.find_all('script'):
                if script.string and any(x in script.string for x in ['HB', 'SB', 'HJ', 'SJ']):
                    matches = re.findall(regex_pattern, script.string.replace(" ", ""))
                    found_bills.update([m.upper() for m in matches])
            
            text = soup.get_text(separator=' ')
            matches = re.findall(regex_pattern, text.replace(" ", ""))
            found_bills.update([m.upper() for m in matches])
            
    except Exception: pass
    return sorted(list(found_bills)), False

def run_calendar_update():
    http_session = get_armored_session()
    
    session_data = get_active_session_info(http_session)
    if not session_data:
        print("🚨 CRITICAL: Failed to retrieve active session from State API.")
        print("🛡️ Safety Triggered: Aborting run to protect Google Sheet from data wipe.")
        sys.exit(1) 
        
    ACTIVE_SESSION = session_data["code"]
    test_start_date = session_data["start"]
    test_end_date = session_data["end"]

    print("🔐 Authenticating with Google Cloud...")
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json: 
        print("🚨 CRITICAL: GCP Credentials missing.")
        sys.exit(1)
        
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    sheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sheet.worksheet("Sheet1")

    blob_code = f"20{ACTIVE_SESSION}" if len(ACTIVE_SESSION) == 3 else ACTIVE_SESSION

    master_events = []
    convene_times = {}
    api_schedule_map = {}
    docket_memory = {} 

    print("📡 Downloading Official DOCKET.CSV...")
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
                    if b_num not in docket_memory[date_str]: docket_memory[date_str][b_num] = []
                    docket_memory[date_str][b_num].append(c_name)

    print("📡 Downloading Live API Schedule & Agendas...")
    try:
        sched_res = http_session.get("https://lis.virginia.gov/Schedule/api/getschedulelistasync", headers=HEADERS, params={"sessionCode": ACTIVE_SESSION}, timeout=10)
        if sched_res.status_code == 200:
            schedules = sched_res.json().get('Schedules', []) if isinstance(sched_res.json(), dict) else sched_res.json()
            resolved_parent_map = build_time_graph(schedules)
            
            for meeting in schedules:
                meeting_date = pd.to_datetime(meeting.get('ScheduleDate', '1970-01-01'), errors='coerce')
                if not (test_start_date <= meeting_date <= test_end_date): continue
                date_str = meeting_date.strftime('%Y-%m-%d')
                raw_owner_name = str(meeting.get('OwnerName', '')).strip()
                owner_lower = raw_owner_name.lower()
                is_cancelled = meeting.get('IsCancelled', False)
                status = "CANCELLED" if is_cancelled else ""
                
                raw_time = str(meeting.get('ScheduleTime', '')).strip()
                raw_desc = str(meeting.get('Description', ''))
                clean_desc = re.sub(r'<[^>]+>', '', raw_desc).strip()
                
                agenda_url = None
                link_match = re.search(r'href=[\'"]?([^\'" >]+)', raw_desc)
                if link_match and any(x in raw_desc.lower() for x in ["agenda", "docket", "info"]):
                    agenda_url = link_match.group(1)
                
                sort_time_24h = resolved_parent_map.get(owner_lower, "23:59")
                time_val = raw_time
                dynamic_markers = ["upon adjournment", "minutes after", "hour after", "recess"]
                stitched_text = f"{raw_time} {clean_desc}"
                if any(m in stitched_text.lower() for m in dynamic_markers):
                    for part in stitched_text.split(';'):
                        if any(m in part.lower() for m in dynamic_markers):
                            time_val = part.strip(); break
                            
                if not time_val: time_val = "Time TBA"
                
                normalized_name = raw_owner_name
                chamber_prefix = "House " if "house" in owner_lower else "Senate " if "senate" in owner_lower else ""
                for api_name, aliases in LOCAL_LEXICON.items():
                    if api_name.startswith(chamber_prefix):
                        if any(alias in owner_lower for alias in aliases):
                            normalized_name = api_name; break

                if "house convenes" in owner_lower or "house chamber" in owner_lower:
                    if date_str not in convene_times: convene_times[date_str] = {}
                    convene_times[date_str]["House"] = {"Time": time_val, "SortTime": sort_time_24h, "Name": normalized_name}
                elif "senate convenes" in owner_lower or "senate chamber" in owner_lower:
                    if date_str not in convene_times: convene_times[date_str] = {}
                    convene_times[date_str]["Senate"] = {"Time": time_val, "SortTime": sort_time_24h, "Name": normalized_name}
                
                map_key = f"{date_str}_{normalized_name}"
                if map_key not in api_schedule_map: api_schedule_map[map_key] = {"Time": time_val, "SortTime": sort_time_24h, "Status": status}
                
                if any(k in owner_lower for k in ["caucus", "session", "floor", "convenes", "adjourned"]):
                    master_events.append({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name if normalized_name else "Chamber Event", "Bill": clean_desc, "Outcome": "", "AgendaOrder": -1, "Source": "API"})
                    continue
                
                has_docket = False
                combined_bills = set()
                dlq_flag = ""
                
                if agenda_url and not is_cancelled:
                    extracted_bills, is_corrupt = extract_rogue_agenda(agenda_url, http_session, meeting_date)
                    combined_bills.update(extracted_bills)
                    if is_corrupt: dlq_flag = "⚠️ [Agenda unreadable - Manual check required]"
                
                if date_str in docket_memory:
                    for b_num, comm_list in docket_memory[date_str].items():
                        if any(normalized_name.lower().strip() == c.lower().strip() for c in comm_list):
                            combined_bills.add(b_num)
                            
                if combined_bills:
                    for bill in sorted(list(combined_bills)):
                        master_events.append({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name, "Bill": bill, "Outcome": "Scheduled", "AgendaOrder": 1, "Source": "DOCKET"})
                        if date_str not in docket_memory: docket_memory[date_str] = {}
                        if bill not in docket_memory[date_str]: docket_memory[date_str][bill] = []
                        if normalized_name not in docket_memory[date_str][bill]: docket_memory[date_str][bill].append(normalized_name)
                    has_docket = True

                if dlq_flag:
                    master_events.append({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name, "Bill": dlq_flag, "Outcome": "", "AgendaOrder": 0, "Source": "API_Skeleton"})
                    has_docket = True

                if not has_docket:
                    if sort_time_24h == "06:00" and "after" in time_val.lower():
                        clean_desc = f"⚠️ Time Unverified (Check Parent) - {clean_desc}"
                    master_events.append({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name, "Bill": clean_desc if clean_desc else "No agenda listed.", "Outcome": "", "AgendaOrder": -1, "Source": "API_Skeleton"})
                    
    except Exception as e: print(f"🚨 API Schedule failed: {e}")

    print("📡 Processing HISTORY.CSV via Chain of Custody...")
    df_past = safe_fetch_csv(f"https://blob.lis.virginia.gov/lisfiles/{blob_code}/HISTORY.CSV")
    if df_past.empty:
        df_past = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
        
    if not df_past.empty:
        bill_col = next((c for c in df_past.columns if 'bill' in c.lower()), 'BillNumber')
        date_col = next((c for c in df_past.columns if 'date' in c.lower()), 'HistoryDate')
        desc_col = next((c for c in df_past.columns if 'desc' in c.lower() or 'action' in c.lower()), 'Description')
        df_past['CleanBill'] = df_past[bill_col].astype(str).str.replace(' ', '').str.upper()
        df_past['ParsedDate'] = pd.to_datetime(df_past[date_col], errors='coerce')
        df_past = df_past[(df_past['ParsedDate'] >= test_start_date) & (df_past['ParsedDate'] <= test_end_date)]
        
        df_past['OriginalOrder'] = range(len(df_past))
        df_past = df_past.sort_values(by=['ParsedDate', 'OriginalOrder'])
        
        pattern = '|'.join(['report', 'continue', 'pass', 'fail', 'incorporate', 'hearing', 'strike', 'stricken', 'veto', 'sign', 'agreed', 'read', 'refer', 'waive', 'recommend', 'receive', 'release', 'take', 'conferee', 'amendment', 'substitute'])
        df_past = df_past[df_past[desc_col].str.contains(pattern, case=False, na=False)]
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
            for api_name, aliases in LOCAL_LEXICON.items():
                if api_name.startswith(chamber_prefix):
                    for alias in aliases:
                        if alias and alias in outcome_lower:
                            matched_committee = api_name; break
                if matched_committee: break

            display_verbs = ["reported from", "continued in", "passed by indefinitely in", "discharged from"]
            if matched_committee and any(v in outcome_lower for v in display_verbs):
                event_location = matched_committee

            routing_verbs = ["referred to", "re-referred to", "assigned to", "placed on"]
            if any(v in outcome_lower for v in routing_verbs):
                if matched_committee: bill_locations[bill_num] = matched_committee
            elif "reported from" in outcome_lower or "discharged from" in outcome_lower:
                bill_locations[bill_num] = chamber_prefix + "Floor"

            floor_reset_phrases = ["read first", "read second", "read third", "passed house", "passed senate", "agreed to", "rejected", "signed by", "presented", "received", "enrolled", "engrossed", "conferees:"]
            if any(p in outcome_lower for p in floor_reset_phrases):
                event_location = chamber_prefix + "Floor"
                bill_locations[bill_num] = chamber_prefix + "Floor"

            allowed_rooms = docket_memory.get(date_str, {}).get(bill_num, [])
            if allowed_rooms and matched_committee:
                for room in allowed_rooms:
                    if matched_committee.lower() in room.lower():
                        event_location = room; break

            all_committee_verbs = display_verbs + routing_verbs
            if any(v in outcome_lower for v in all_committee_verbs) and not matched_committee and "floor" not in outcome_lower:
                event_location = f"⚠️ [Unmapped] {outcome_text.split(' from ')[-1].split(' to ')[-1]} (Ledger)"

            noise_words = ["impact statement", "substitute printed", "laid on speaker's table", "laid on clerk's desk", "presented", "reprinted", "engrossed by senate - committee substitute", "engrossed by house - committee substitute"]
            if any(n in outcome_lower for n in noise_words): continue
            
            time_val = "Ledger"
            sort_time_24h = "23:59"
            status = ""
            api_key = f"{date_str}_{event_location}"
            
            if api_key not in api_schedule_map:
                alt_key_1 = f"{api_key} Committee"
                alt_key_2 = api_key.replace(" Committee", "")
                if alt_key_1 in api_schedule_map:
                    api_key = alt_key_1; event_location = f"{event_location} Committee"
                elif alt_key_2 in api_schedule_map:
                    api_key = alt_key_2; event_location = event_location.replace(" Committee", "")
            
            if api_key in api_schedule_map:
                time_val = api_schedule_map[api_key]["Time"]
                sort_time_24h = api_schedule_map[api_key]["SortTime"]
                status = api_schedule_map[api_key]["Status"]
            else:
                if "passed by" in outcome_lower and "Floor" not in event_location:
                    event_location = f"⚠️ [Location Unknown] Passed by for the day (Ledger)"
            
            if "Floor" in event_location:
                anchor = convene_times.get(date_str, {}).get(chamber_prefix.strip())
                if anchor: time_val, sort_time_24h, event_location = anchor["Time"], anchor["SortTime"], anchor["Name"]
                
            master_events.append({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": event_location, "Bill": bill_num, "Outcome": outcome_text, "AgendaOrder": 999, "Source": "CSV"})

    print("🧹 Cleaning Data...")
    final_df = pd.DataFrame(master_events)
    if not final_df.empty:
        final_df = final_df[~((final_df['Bill'] == "No agenda listed.") & final_df.duplicated(subset=['Date', 'Committee', 'Time'], keep=False))]
        final_df = final_df.sort_values(by=['Date', 'Committee', 'Bill', 'Source'])
        final_df = final_df.drop_duplicates(subset=['Date', 'Committee', 'Bill'], keep='last')
        final_df = final_df.fillna("")
        sheet_data = [final_df.columns.values.tolist()] + final_df.values.tolist()
        print("💾 Writing to Enterprise Database...")
        worksheet.clear()
        worksheet.update(values=sheet_data, range_name="A1")
        print("✅ SUCCESS: The Final Mastermind Build is complete.")
    else:
        print("⚠️ No data generated for the window.")

if __name__ == "__main__": 
    run_calendar_update()
