# --- SOURCE: OFFICIAL SCHEDULE PAGES (The Bulletin Board) ---
@st.cache_data(ttl=300)
def fetch_chamber_homepage_time(chamber):
    """
    Scrapes the SPECIFIC schedule pages where session times are listed.
    """
    if chamber == "House":
        # The House has a dedicated schedule page
        url = "https://house.vga.virginia.gov/schedule/meetings"
    else:
        # The Senate time is most reliably found on the LIS homepage or their calendar
        url = "https://lis.virginia.gov/"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = session.get(url, headers=headers, timeout=5)
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        # Capture raw text for debug
        raw_preview = text[:2000] # Grab a bit more context
        
        # --- REGEX STRATEGY ---
        # We look for "[Time] [Chamber] Convenes" pattern which is common on these specific pages
        
        if chamber == "House":
            # Matches: "12:00 PM House Convenes" or "House Convenes at 12:00 PM"
            # The page usually lists: "12:00 PM House Convenes"
            match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP][mM])\.?\s+House\s+Convenes', text, re.IGNORECASE)
            if not match:
                # Fallback for "House Convenes... 12:00 PM"
                match = re.search(r'House\s+Convenes.*(\d{1,2}:\d{2}\s*[aA|pP][mM])', text[:5000], re.IGNORECASE)
        else:
            # Senate (on LIS homepage): "* 12:00 PM Senate Convenes"
            match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP][mM])\.?\s+Senate\s+Convenes', text, re.IGNORECASE)

        if match:
            # Found it!
            return match.group(1).upper(), f"Found on Official Schedule ({url})", raw_preview
            
        return None, f"Checked Schedule Page ({url}) - No time found", raw_preview
        
    except Exception as e:
        return None, f"Scrape Error: {str(e)}", f"Error: {str(e)}"
