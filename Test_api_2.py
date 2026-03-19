import pandas as pd
import requests
import io

print("🚀 Initiating LIS Docket Probe...")

# 1. Target the live 2026 Regular Session Docket Blob
ACTIVE_SESSION = "20261"
DOCKET_URL = f"https://lis.blob.core.windows.net/lisfiles/{ACTIVE_SESSION}/DOCKET.CSV"

try:
    print(f"📡 Downloading raw docket from: {DOCKET_URL}")
    response = requests.get(DOCKET_URL, timeout=10)
    response.raise_for_status()
    
    # 2. Parse the CSV
    # VA LIS CSVs often have weird encoding, so we use ISO-8859-1
    doc_df = pd.read_csv(io.StringIO(response.text), encoding='ISO-8859-1', on_bad_lines='skip')
    
    # Clean the headers so we can read them easily
    doc_df.columns = doc_df.columns.str.strip()
    
    print("\n✅ DATA EXTRACTED SUCCESSFULLY.")
    print("-" * 50)
    
    # 3. THE RECONNAISSANCE 
    print("📋 RAW COLUMNS PROVIDED BY THE STATE:")
    for i, col in enumerate(doc_df.columns):
        print(f"  {i+1}. {col}")
        
    print("-" * 50)
    
    # 4. TEST EXTRACTION: Let's look at the agenda for a specific date
    # (Checking if they give us Agenda Order or Block Voting details)
    print("🔍 SAMPLE AGENDA DATA (First 5 Rows):")
    if not doc_df.empty:
        # Displaying the most relevant columns we expect to see
        display_cols = [c for c in doc_df.columns if c.lower() in ['com_name', 'committee_name', 'doc_date', 'meeting_date', 'bill_no', 'bill_number', 'seq_no', 'sequence']]
        
        if display_cols:
            print(doc_df[display_cols].head(5).to_string(index=False))
        else:
            print(doc_df.head(5).to_string(index=False))
            
except Exception as e:
    print(f"❌ PROBE FAILED: {e}")
