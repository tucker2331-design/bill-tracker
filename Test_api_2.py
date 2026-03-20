# ==========================================
# 2. THE EXTRACTOR (Enterprise Reverse-Lookup)
# ==========================================
@st.cache_data(ttl=600)
def build_master_calendar(sessions, tracked_bills, bypass):
    master_events = []
    
    def safe_fetch_csv(url):
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200 and "<?xml" not in res.text[:20]:
                df = pd.read_csv(io.StringIO(res.text))
                return df.rename(columns=lambda x: x.strip())
        except: pass
        return pd.DataFrame()

    with st.spinner("📥 Synchronizing JSON Data Keys (3-Week Window)..."):
        for session in sessions:
            api_code = session["api"]
            blob_code = session["blob"]
            is_special = session["is_special"]
            
            # --- 1. Rosetta Stone ---
            rosetta_stone = {}
            try:
                for chamber in ['H', 'S']:
                    comm_res = requests.get("https://lis.virginia.gov/Committee/api/getcommitteelistasync", headers=HEADERS, params={"sessionCode": api_code, "chamberCode": chamber}, timeout=5)
                    if comm_res.status_code == 200:
                        for c in comm_res.json():
                            prefix = "House " if chamber == 'H' else "Senate "
                            rosetta_stone[prefix + str(c.get('ComDes')).strip()] = c.get('ComCode')
            except Exception as e: print(f"Rosetta failed: {e}")

            # --- 2. Build Schedule Skeleton ---
            api_schedule_map = {} 
            try:
                sched_res = requests.get("https://lis.virginia.gov/Schedule/api/getschedulelistasync", headers=HEADERS, params={"sessionCode": api_code}, timeout=5)
                if sched_res.status_code == 200:
                    schedules = sched_res.json()
                    if isinstance(schedules, dict): schedules = schedules.get('Schedules', [])
                    
                    for meeting in schedules:
                        meeting_date = pd.to_datetime(meeting.get('ScheduleDate', '1970-01-01'), errors='coerce')
                        
                        # SPEED OPTIMIZATION: Only process meetings inside our 3-week test window!
                        if not (past_week_2_start <= meeting_date <= future_end):
                            continue
                            
                        date_str = meeting_date.strftime('%Y-%m-%d')
                        owner_name = str(meeting.get('OwnerName', '')).strip()
                        chamber = meeting.get('ChamberCode')
                        if not chamber: chamber = 'S' if 'Senate' in owner_name else 'H'
                        
                        # Fix 1: True Boolean Cancellation Check
                        is_cancelled = meeting.get('IsCancelled', False)
                        status = "CANCELLED" if is_cancelled else ""
                        
                        # Fix 2: Dynamic Time Extraction
                        raw_time = str(meeting.get('ScheduleTime', '')).strip()
                        raw_desc = str(meeting.get('Description', meeting.get('ScheduleDesc', ''))).strip()
                        clean_desc = re.sub(r'<[^>]+>', '', raw_desc).strip() # Strip HTML tags
                        
                        time_val = raw_time
                        dynamic_markers = ["upon adjournment", "minutes after", "to be determined", "tba"]
                        
                        if any(marker in clean_desc.lower() for marker in dynamic_markers):
                            parts = clean_desc.split(';')
                            for part in parts:
                                if any(marker in part.lower() for marker in dynamic_markers):
                                    time_val = part.strip()
                                    break
                        if not time_val: time_val = "Time TBA"
                        
                        api_schedule_map[f"{date_str}_{owner_name}"] = {"Time": time_val, "Status": status}
                        
                        # Caucuses & Sessions bypass
                        if any(k in owner_name.lower() for k in ["caucus", "session", "floor", "convenes", "adjourned"]):
                            master_events.append({
                                "Date": date_str, "Time": time_val, "Status": status,
                                "Committee": owner_name if owner_name else "Chamber Event",
                                "Bill": "📌 " + clean_desc,
                                "Outcome": "", "AgendaOrder": -1,
                                "IsFuture": meeting_date >= pd.to_datetime(TODAY.strftime('%Y-%m-%d')), "Source": "API"
                            })
                            continue
                        
                        # Fix 3: Subcommittee Bridge
                        committee_id = meeting.get('CommitteeNumber', meeting.get('CommitteeCode'))
                        if not committee_id:
                            committee_id = rosetta_stone.get(owner_name)
                            if not committee_id and "-" in owner_name:
                                parent_name = owner_name.split('-')[0].strip()
                                committee_id = rosetta_stone.get(parent_name)
                            
                        has_docket_bills = False
                        if committee_id and not is_cancelled:
                            doc_res = requests.get("https://lis.virginia.gov/Committee/api/getdocketlistasync", headers=HEADERS, params={"sessionCode": api_code, "chamberCode": chamber, "committeeID": committee_id}, timeout=5)
                            if doc_res.status_code == 200 and doc_res.json():
                                agendas = doc_res.json()
                                has_docket_bills = True
                                for item in agendas:
                                    bill_num = str(item.get('LegislationNumber', '')).replace(' ', '').upper()
                                    if is_special: bill_num += " [Special]"
                                    if bypass or bill_num.split(' ')[0] in tracked_bills:
                                        master_events.append({
                                            "Date": date_str, "Time": time_val, "Status": status,
                                            "Committee": owner_name, "Bill": bill_num,
                                            "Outcome": item.get('Description', 'Pending Hearing'),
                                            "AgendaOrder": item.get('Sequence', 0),
                                            "IsFuture": meeting_date >= pd.to_datetime(TODAY.strftime('%Y-%m-%d')), "Source": "API"
                                        })
                        
                        if not has_docket_bills:
                            master_events.append({
                                "Date": date_str, "Time": time_val, "Status": status,
                                "Committee": owner_name, "Bill": "📌 No live docket",
                                "Outcome": "", "AgendaOrder": -1,
                                "IsFuture": meeting_date >= pd.to_datetime(TODAY.strftime('%Y-%m-%d')), "Source": "API"
                            })
            except Exception as e: print(f"Schedule extraction failed: {e}")

            # --- 3. CSV Stitching (Historical Fallback) ---
            df_past = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
            if not df_past.empty:
                bill_col = next((c for c in df_past.columns if 'bill' in c.lower()), 'BillNumber')
                date_col = next((c for c in df_past.columns if 'date' in c.lower()), 'HistoryDate')
                desc_col = next((c for c in df_past.columns if 'desc' in c.lower() or 'action' in c.lower()), 'Description')
                
                df_past['CleanBill'] = df_past[bill_col].astype(str).str.replace(' ', '').str.upper()
                if is_special: df_past['CleanBill'] = df_past['CleanBill'] + " [Special]"
                
                df_past['ParsedDate'] = pd.to_datetime(df_past[date_col], errors='coerce')
                mask = (df_past['ParsedDate'] >= pd.to_datetime(past_week_2_start)) & (df_past['ParsedDate'] <= pd.to_datetime(TODAY))
                df_past = df_past[mask]
                
                pattern = '|'.join(['report', 'continue', 'pass', 'fail', 'incorporate', 'hearing', 'strike', 'stricken', 'veto', 'sign', 'agreed', 'read'])
                df_past = df_past[df_past[desc_col].str.contains(pattern, case=False, na=False)]
                
                if not bypass: df_past = df_past[df_past['CleanBill'].str.split(' ').str[0].isin(tracked_bills)]
                
                official_committees = sorted(rosetta_stone.keys(), key=len, reverse=True)
                
                for _, row in df_past.iterrows():
                    outcome_text = str(row[desc_col])
                    outcome_lower = outcome_text.lower()
                    date_str = row['ParsedDate'].strftime('%Y-%m-%d')
                    chamber_prefix = "House " if str(row['CleanBill']).startswith('H') else "Senate "
                    
                    committee_name = None
                    floor_keywords = ["passed", "agreed", "engrossed", "read third", "signed", "enrolled", "reconsideration"]
                    if any(k in outcome_lower for k in floor_keywords) and not any(k in outcome_lower for k in ["reported", "referred"]):
                        committee_name = chamber_prefix + "Floor"
                    else:
                        for off_comm in official_committees:
                            base_name = off_comm.replace("House ", "").replace("Senate ", "").lower()
                            if base_name in outcome_lower and off_comm.startswith(chamber_prefix):
                                committee_name = off_comm
                                break
                        if not committee_name:
                            committee_name = chamber_prefix + "Floor"

                    time_val = "Ledger"
                    status = ""
                    api_key = f"{date_str}_{committee_name}"
                    
                    if api_key in api_schedule_map:
                        time_val = api_schedule_map[api_key]["Time"]
                        status = api_schedule_map[api_key]["Status"]
                        
                    master_events.append({
                        "Date": date_str, "Time": time_val, "Status": status,
                        "Committee": committee_name, "Bill": row['CleanBill'],
                        "Outcome": outcome_text, "AgendaOrder": 999,
                        "IsFuture": False, "Source": "CSV"
                    })

    final_df = pd.DataFrame(master_events)
    if not final_df.empty:
        final_df = final_df[~((final_df['Bill'] == "📌 No live docket") & 
                              final_df.duplicated(subset=['Date', 'Committee'], keep=False))]
        final_df = final_df.sort_values(by=['Date', 'Committee', 'Bill', 'Source'])
        final_df = final_df.drop_duplicates(subset=['Date', 'Committee', 'Bill'], keep='first')
        
    return final_df
