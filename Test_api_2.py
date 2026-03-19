import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="LIS Docket Probe", layout="wide")

st.title("🚀 LIS Docket Data Probe")

# 1. Target the live 2026 Regular Session Docket Blob
ACTIVE_SESSION = "20261"
DOCKET_URL = f"https://lis.blob.core.windows.net/lisfiles/{ACTIVE_SESSION}/DOCKET.CSV"

try:
    st.info(f"📡 Downloading raw docket from: {DOCKET_URL}")
    response = requests.get(DOCKET_URL, timeout=10)
    response.raise_for_status()
    
    # 2. Parse the CSV
    # VA LIS CSVs often have weird encoding, so we use ISO-8859-1
    doc_df = pd.read_csv(io.StringIO(response.text), encoding='ISO-8859-1', on_bad_lines='skip')
    
    # Clean the headers so we can read them easily
    doc_df.columns = doc_df.columns.str.strip()
    
    st.success("✅ DATA EXTRACTED SUCCESSFULLY.")
    st.divider()
    
    # 3. THE RECONNAISSANCE 
    st.subheader("📋 RAW COLUMNS PROVIDED BY THE STATE:")
    st.write("Here are the exact column headers the state provides us in the CSV:")
    st.code(list(doc_df.columns))
    
    st.divider()
    
    # 4. TEST EXTRACTION: Let's look at the agenda data
    st.subheader("🔍 SAMPLE AGENDA DATA (First 50 Rows):")
    st.write("Do we have a sequence number? Do we have a time?")
    if not doc_df.empty:
        # Displaying the most relevant columns we expect to see
        display_cols = [c for c in doc_df.columns if c.lower() in ['com_name', 'committee_name', 'doc_date', 'meeting_date', 'bill_no', 'bill_number', 'seq_no', 'sequence']]
        
        if display_cols:
            st.dataframe(doc_df[display_cols].head(50), use_container_width=True)
        else:
            st.dataframe(doc_df.head(50), use_container_width=True)
            
except Exception as e:
    st.error(f"❌ PROBE FAILED: {e}")
