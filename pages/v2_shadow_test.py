import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="V3 UI Test", layout="wide")
st.title("⚡ V3 Mastermind UI (Shadow Test)")
st.info("Reading directly from the Ghost Worker's Mastermind Database. Live app.py is untouched.")

# --- THE DATABASE CONNECTION ---
# This is the direct CSV export link to your new Mastermind Google Sheet
SHEET_ID = "1566pCv70iQ7YkTQK71RfYerciK-ukW-QdblTu2-Prfw"
DB_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sheet1"

@st.cache_data(ttl=60)
def load_mastermind_db():
    try:
        # 1. Download the flat database
        df = pd.read_csv(DB_URL)
        
        # 2. The Magic Unpack: Convert the text strings back into Python lists
        df['History_Data'] = df['History_Data'].apply(lambda x: json.loads(x) if pd.notna(x) else [])
        df['Upcoming_Meetings'] = df['Upcoming_Meetings'].apply(lambda x: json.loads(x) if pd.notna(x) else [])
        
        return df
    except Exception as e:
        st.error(f"Failed to load database: {e}")
        return pd.DataFrame()

# --- LOAD AND DISPLAY ---
with st.spinner("Fetching pre-processed database..."):
    db_df = load_mastermind_db()

if not db_df.empty:
    st.success(f"✅ Successfully loaded {len(db_df)} bills in record time!")
    
    # Let's do a quick test render of HB1 to prove the UI can read the unpacked history
    st.subheader("🔍 Integration Proof: HB1 Render Test")
    
    hb1_row = db_df[db_df['Bill Number'] == 'HB1'].iloc[0] if not db_df[db_df['Bill Number'] == 'HB1'].empty else None
    
    if hb1_row is not None:
        with st.expander(f"**{hb1_row['Bill Number']}** - {hb1_row['Official Title']}", expanded=True):
            st.markdown(f"**Folder:** {hb1_row['Auto_Folder']} | **Lifecycle:** {hb1_row['Lifecycle']}")
            st.markdown(f"**Current Location:** {hb1_row['Display_Committee']}")
            st.markdown(f"**Status:** {hb1_row['Status']}")
            
            st.markdown("**📜 Unpacked History Timeline:**")
            # Because we unpacked the JSON, Streamlit can instantly render it as a dataframe!
            if hb1_row['History_Data']:
                st.dataframe(pd.DataFrame(hb1_row['History_Data']), hide_index=True, use_container_width=True)
            else:
                st.caption("No history found.")
    else:
        st.warning("HB1 not found in database yet. Did the Ghost Worker finish running?")

    st.divider()
    st.subheader("Raw Database View")
    st.dataframe(db_df.head(50), use_container_width=True)
