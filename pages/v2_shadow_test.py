# --- PROCESS MEETINGS ---
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: continue
    
    name = m.get("OwnerName", "")
    if "Caucus" in name or "Press" in name: continue
    
    # 0. IDENTIFY FLOOR SESSIONS
    # We flag these so they can bypass the "Ghost Protocol" later
    is_floor_session = "Convene" in name or "Session" in name or "House of Delegates" == name or "Senate" == name
    
    api_time = m.get("ScheduleTime")
    api_comments = m.get("Comments") or ""
    description_html = m.get("Description") or ""
    
    final_time = "TBD"
    status_label = "Active"
    decision_log = [] 
    
    # 1. API STANDARD CHECK
    # We trust the API if it gives us a real time
    if api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time
        decision_log.append("✅ Found in API 'ScheduleTime'")

    # 2. FLOOR SESSION FIX (The Front Door Strategy)
    # If API failed, try the Homepage Scraper. 
    # IF SCRAPER FAILS: We leave it as "TBD". We do NOT inject 12:00 PM.
    if final_time == "TBD" and is_floor_session:
        chamber = "House" if "House" in name else "Senate"
        if chamber in homepage_time_cache:
            time_found, source_log = homepage_time_cache[chamber]
            if time_found:
                final_time = time_found
                decision_log.append(f"✅ {source_log}")
            else:
                decision_log.append(f"⚠️ {source_log}")

    # 3. API COMMENTS MINING
    if final_time == "TBD":
        t = extract_complex_time(api_comments)
        if t: 
            final_time = t
            decision_log.append("✅ Found in API 'Comments'")

    # 4. DESCRIPTION MINING
    if final_time == "TBD":
        t = extract_complex_time(description_html)
        if t: 
            final_time = t
            decision_log.append("✅ Found in API 'Description'")

    # 5. CROSS-REFERENCE VALIDATOR (Zombie Check)
    # Only run this on Committees. Floor sessions are often implicit in the schedule.
    if final_time == "TBD" and not is_floor_session:
        if m_date in lis_daily_cache:
            official_text = lis_daily_cache[m_date]
            tokens = set(name.replace("-", " ").lower().split())
            tokens -= {"house", "senate", "committee", "subcommittee"}
            
            if tokens:
                found_in_official = False
                for t in tokens:
                    if len(t) > 3 and t in official_text.lower():
                        found_in_official = True
                        break
                
                if not found_in_official:
                    final_time = "❌ Not on Daily Schedule"
                    status_label = "Cancelled"
                    decision_log.append(f"🧟 Zombie Detected: Not in LIS DCO")
                else:
                    decision_log.append("ℹ️ Verified in Official Schedule")

    # 6. GHOST PROTOCOL (The Fix)
    agenda_link = extract_agenda_link(description_html)
    
    if "Cancel" in str(final_time) or "Not on" in str(final_time):
        status_label = "Cancelled"
    
    elif final_time == "TBD":
        if not agenda_link:
            # === THE CHANGE IS HERE ===
            if is_floor_session:
                # If it's a Floor Session, let it live even without a time/link.
                final_time = "Time TBA"
                status_label = "Active"
                decision_log.append("🏛️ Floor Session Confirmed (Waiting for Time)")
            else:
                # If it's a Committee without a link/time, kill it.
                final_time = "❌ Not Meeting"
                status_label = "Cancelled" 
                decision_log.append("👻 Ghost Protocol: No Link + No Time")
        else:
            final_time = "⚠️ Time Not Listed"
            status_label = "Warning"
            decision_log.append("⚠️ Time missing from all sources")

    m['DisplayTime'] = final_time
    m['AgendaLink'] = agenda_link
    m['Status'] = status_label
    m['Log'] = decision_log
    
    week_map[m_date].append(m)
