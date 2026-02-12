def get_bill_data_batch(bill_numbers, lis_data_dict):
    lis_df = lis_data_dict.get('bills', pd.DataFrame())
    history_df = lis_data_dict.get('history', pd.DataFrame())
    docket_df = lis_data_dict.get('docket', pd.DataFrame())
    
    results = []
    clean_bills = list(set([clean_bill_id(b) for b in bill_numbers if str(b).strip() != 'nan']))
    
    lis_lookup = {}
    if not lis_df.empty and 'bill_clean' in lis_df.columns:
        lis_lookup = lis_df.set_index('bill_clean').to_dict('index')

    history_lookup = {}
    if not history_df.empty and 'bill_clean' in history_df.columns:
        for b_id, group in history_df.groupby('bill_clean'):
            history_lookup[b_id] = group.to_dict('records')
            
    docket_lookup = {}
    if not docket_df.empty and 'bill_clean' in docket_df.columns:
        for b_id, group in docket_df.groupby('bill_clean'):
            docket_lookup[b_id] = group.to_dict('records')

    for bill_num in clean_bills:
        item = lis_lookup.get(bill_num)
        title = "Unknown"; status = "Not Found"; date_val = ""; curr_comm = "-"; curr_sub = "-"; history_data = []
        
        # --- NEW LOGIC: LATEST DATE WINS ---
        # Instead of prioritizing House/Senate based on bill type, we check dates.
        if item:
            title = item.get('bill_description', 'No Title')
            
            # 1. Extract House Data
            h_act = str(item.get('last_house_action', ''))
            h_date_str = str(item.get('last_house_action_date', ''))
            h_date = datetime.min.date()
            try: h_date = datetime.strptime(h_date_str, "%Y-%m-%d").date()
            except: pass

            # 2. Extract Senate Data
            s_act = str(item.get('last_senate_action', ''))
            s_date_str = str(item.get('last_senate_action_date', ''))
            s_date = datetime.min.date()
            try: s_date = datetime.strptime(s_date_str, "%Y-%m-%d").date()
            except: pass

            # 3. Compare and Select the Winner
            if s_date > h_date:
                status = s_act
                date_val = s_date_str
            elif h_date > s_date:
                status = h_act
                date_val = h_date_str
            else:
                # Dates are equal: Use the one that isn't empty, or default to House if both exist
                if not h_act and s_act:
                    status = s_act
                    date_val = s_date_str
                else:
                    status = h_act
                    date_val = h_date_str
            
            # Fallback if both empty
            if not status or status == 'nan':
                status = "Introduced"

        # --- END NEW LOGIC ---

        raw_history = history_lookup.get(bill_num, [])
        history_blob = ""
        if raw_history:
            for h_row in raw_history:
                desc = ""; date_h = ""
                for col in ['history_description', 'description', 'action', 'history']:
                    if col in h_row and pd.notna(h_row[col]): desc = str(h_row[col]); break
                for col in ['history_date', 'date', 'action_date']:
                    if col in h_row and pd.notna(h_row[col]): date_h = str(h_row[col]); break
                if desc:
                    history_data.append({"Date": date_h, "Action": desc})
                    history_blob += desc.lower() + " "
                    desc_lower = desc.lower()
                    if "referred to" in desc_lower:
                        match = re.search(r'referred to (?:committee on|the committee on)?\s?([a-z\s&,-]+)', desc_lower)
                        if match: found = match.group(1).strip().title(); curr_comm = found if len(found) > 3 else curr_comm
                    if "sub:" in desc_lower:
                        try: curr_sub = desc_lower.split("sub:")[1].strip().title()
                        except: pass
        
        # --- GROUND UP PIN LOGIC ---
        # Now that 'status' and 'date_val' are guaranteed to be the LATEST action,
        # we can verify against history to see if the history file is lagging.
        
        # 1. Identify Dates
        status_date_obj = None
        try: status_date_obj = datetime.strptime(str(date_val), "%Y-%m-%d").date()
        except: pass

        latest_hist_date_obj = None
        if history_data:
            dates = []
            for h in history_data:
                try: dates.append(datetime.strptime(str(h['Date']), "%Y-%m-%d").date())
                except: pass
            if dates: latest_hist_date_obj = max(dates)

        # 2. Check for Content Duplication (fuzzy match)
        status_text_clean = str(status).strip().lower()
        is_in_history = any(status_text_clean in str(h['Action']).lower() for h in history_data)

        # 3. Check for Low-Value "Junk"
        junk_triggers = ["fiscal impact", "statement from", "vote detail", "introduced", "assigned", "placed on", "offered"]
        is_junk = any(j in status_text_clean for j in junk_triggers)

        # 4. EXECUTE PIN
        should_pin = False
        # Only pin if Status date is NEWER than history, or equal but text is missing
        is_status_newer = False
        if status_date_obj and latest_hist_date_obj:
            if status_date_obj >= latest_hist_date_obj: is_status_newer = True
        elif status_date_obj and not latest_hist_date_obj:
            is_status_newer = True

        if is_status_newer and not is_in_history and not is_junk:
            should_pin = True

        if should_pin:
             history_data.append({"Date": date_val, "Action": f"📍 {str(status).strip()}"})
        # --- END GROUND UP LOGIC ---

        if curr_comm == "-":
            val = item.get('last_house_committee')
            if not val or str(val) == 'nan':
                act_id = str(item.get('last_actid', ''))
                if len(act_id) >= 3:
                    code = act_id[:3]
                    if code in COMMITTEE_MAP: curr_comm = COMMITTEE_MAP[code]
            elif str(val) in COMMITTEE_MAP:
                curr_comm = COMMITTEE_MAP[str(val)]
        
        if "pending" in str(status).lower() or "prefiled" in str(status).lower():
            if "referred" not in str(status).lower(): 
                curr_comm = "Unassigned"
        
        if "Courts" in str(curr_comm) and "referred" not in history_blob and "referred" not in str(status).lower():
            curr_comm = "Unassigned"

        curr_comm = clean_committee_name(curr_comm)
        lifecycle = determine_lifecycle(str(status), str(curr_comm), bill_num, history_blob)
        display_comm = curr_comm
        if "Passed" in lifecycle or "Signed" in lifecycle or "Awaiting" in lifecycle:
             if "engross" in str(status).lower(): display_comm = "🏛️ Engrossed (Passed Chamber)"
             elif "read" in str(status).lower(): display_comm = "📜 On Floor (Read/Reported)"
             elif "passed" in str(status).lower(): display_comm = "🎉 Passed Chamber"
             else: display_comm = "On Floor / Reported"

        upcoming_meetings = []
        raw_docket = docket_lookup.get(bill_num, [])
        for d in raw_docket:
            d_date = d.get('meeting_date') or d.get('doc_date')
            d_comm_raw = str(d.get('committee_name', 'Unknown'))
            if "Passed" in lifecycle or "Signed" in lifecycle: d_comm_raw = "Floor Session / Chamber Action"
            elif d_comm_raw == 'Unknown' or d_comm_raw == 'nan': d_comm_raw = curr_comm

            if d_date:
                try:
                    if "/" in str(d_date): dt_obj = datetime.strptime(str(d_date), "%m/%d/%Y")
                    else: dt_obj = datetime.strptime(str(d_date), "%Y-%m-%d")
                    fmt_date = dt_obj.strftime("%Y-%m-%d")
                    upcoming_meetings.append({"Date": fmt_date, "CommitteeRaw": d_comm_raw})
                except: pass

        results.append({
            "Bill Number": bill_num, "Official Title": title, "Status": str(status), "Date": date_val, 
            "Lifecycle": lifecycle, "History_Data": history_data[::-1], 
            "Current_Committee": str(curr_comm).strip(), "Display_Committee": str(display_comm).strip(), 
            "Current_Sub": str(curr_sub).strip(), "Upcoming_Meetings": upcoming_meetings
        })
    return pd.DataFrame(results) if results else pd.DataFrame()
