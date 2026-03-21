import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="CSV X-Ray", layout="wide")
st.title("🔍 Raw CSV Ledger X-Ray (March 6th)")

# Using '261' as the standard blob code for the 2026 Regular Session
BLOB_CODE = "261"
URL = f"https://lis.blob.core.windows.net/lisfiles/{BLOB_CODE}/HISTORY.CSV"

st.write(f"📡 Fetching raw ledger from: `{URL}`")

try:
    res = requests.get(URL, timeout=5)
    if res.status_code == 200:
        # Read the raw CSV
        df = pd.read_csv(io.StringIO(res.text))
        df = df.rename(columns=lambda x: x.strip())
        
        # Find the date column and filter for March 6th
        date_col = next((c for c in df.columns if 'date' in c.lower()), 'HistoryDate')
        desc_col = next((c for c in df.columns if 'desc' in c.lower() or 'action' in c.lower()), 'Description')
        
        df['ParsedDate'] = pd.to_datetime(df[date_col], errors='coerce')
        df_march_6 = df[df['ParsedDate'].dt.strftime('%Y-%m-%d') == '2026-03-06']
        
        st.success(f"✅ Extracted {len(df_march_6)} raw actions for March 6th.")
        
        # Display the raw data, focusing on the Bill Number and the exact Action text
        st.dataframe(df_march_6[['BillNumber', desc_col, date_col]], use_container_width=True)
        
    else:
        st.error(f"Failed to fetch CSV. State server returned: {res.status_code}")
except Exception as e:
    st.error(f"Extraction failed: {e}")
