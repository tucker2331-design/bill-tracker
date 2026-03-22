import os
import json
import requests
import gspread
import pandas as pd
import re
import io
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

print("🚀 Waking up Enterprise Calendar Worker (Strict Scheduling Mode)...")

# --- CONFIGURATION ---
SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

def get_active_session():
    now = datetime.now()
    year = now.year
    years_to_check = [year + 1, year] if now.month >= 11 else [year]
    for y in years_to_check:
        for suffix in ["10", "9", "8", "7", "6", "5", "4", "3", "2", "1"]:
            session_code = f"{y}{suffix}"
            test_url = f"https://lis.blob.core.windows.net/lisfiles/{session_code}/DOCKET.CSV"
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
    except Exception as e: 
        print(f"CSV Fetch Error: {e}")
    return pd.DataFrame()

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
    
    # Target window
    test_start_date = datetime(2026, 3, 4)
    test_end_date = datetime(2026, 3, 10)

    print("📡 Downloading Official DOCKET.CSV...")
    df_docket = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/DOCKET.CSV")
    docket_memory = {} 
    
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
                    # Create a normalized key for matching
                    match_key = f"{date_str}_{c_name.lower().strip()}"
                    if match_key not in docket_memory: docket_memory[match_key] = []
                    docket_memory[match_key].append(b_num)

    print("📡 Downloading Live API Schedule...")
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
                clean_desc = re.sub(r'<[^>]+>', '', str(meeting.get('Description', ''))).strip()
                
                time_val = raw_time
                dynamic_markers = ["upon adjournment", "minutes after", "to be determined", "tba", "recess"]
                if any(m in clean_desc.lower() for m in dynamic_markers):
                    for part in clean_desc.split(';'):
                        if any(m in part.lower() for m in dynamic_markers):
                            time_val = part.strip()
                            break
                if not time_val: time_val = "Time TBA"
                
                # Check the docket memory for bills assigned to this specific meeting
                match_key = f"{date_str}_{owner_name.lower().strip()}"
                scheduled_bills = docket_memory.get(match_key, [])
                
                # If it's a chamber floor session, we leave the bill column to the API description (no docket for floor)
                if any(k in owner_name.lower() for k in ["caucus", "session", "floor", "convenes", "adjourned"]):
                    master_events.append({"Date": date_str, "Time": time_val, "Status": status, "Committee": owner_name if owner_name else "Chamber Event", "Bill": "📌 " + clean_desc, "Outcome": "", "AgendaOrder": -1, "Source": "API"})
                    continue
                
                # If it's a committee meeting, map the docket
                if scheduled_bills:
                    for bill in scheduled_bills:
                        master_events.append({"Date": date_str, "Time": time_val, "Status": status, "Committee": owner_name, "Bill": bill, "Outcome": "Scheduled", "AgendaOrder": 1, "Source": "DOCKET"})
                else:
                    master_events.append({"Date": date_str, "Time": time_val, "Status": status, "Committee": owner_name, "Bill": "📌 No live docket", "Outcome": "", "AgendaOrder": -1, "Source": "API_Skeleton"})
                    
    except Exception as e: print(f"🚨 API Schedule failed: {e}")

    print("🧹 Compiling and Cleaning Data...")
    final_df = pd.DataFrame(master_events)
    if not final_df.empty:
        # Sort and deduplicate
        final_df = final_df.sort_values(by=['Date', 'Committee', 'Bill', 'Source'])
        final_df = final_df.drop_duplicates(subset=['Date', 'Committee', 'Bill'], keep='first')
        
        # Convert to list of lists for Google Sheets
        final_df = final_df.fillna("")
        sheet_data = [final_df.columns.values.tolist()] + final_df.values.tolist()
        
        print("💾 Writing to Enterprise Database...")
        worksheet.clear()
        worksheet.update(values=sheet_data, range_name="A1")
        print("✅ SUCCESS: Pure Scheduling Pipeline complete.")
    else:
        print("⚠️ No data generated for the window.")

if __name__ == "__main__": 
    run_calendar_update()
