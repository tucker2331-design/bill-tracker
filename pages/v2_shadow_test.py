import streamlit as st
import pandas as pd

st.set_page_config(page_title="Diagnostic: CSV Inspector", layout="wide")
st.title("🔬 Diagnostic: CSV Header & Data Inspector")

URL_V94 = "https://lis.blob.core.windows.net/lisfiles/20261/HISTORY.CSV"
URL_DRY_RUN = "https://lis.virginia.gov/cgi-bin/legp604.exe?261+oth+CSV+HISTORY"

st.markdown("This script blindly downloads the data from both sources to see what the column names actually are.")

if st.button("🔍 Run Diagnostic Inspector"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Your original v94 Azure Blob URL")
        try:
            df_v94 = pd.read_csv(URL_V94, encoding='ISO-8859-1', on_bad_lines='skip')
            st.success("Download Successful")
            
            # Show raw columns exactly as Pandas sees them
            st.write("**Raw Column Names:**")
            st.write(df_v94.columns.tolist())
            
            # Show cleaned columns (what our script tries to match against)
            st.write("**Cleaned Column Names (Lowercase/Stripped):**")
            clean_cols_v94 = df_v94.columns.str.strip().str.lower().str.replace(' ', '_').tolist()
            st.write(clean_cols_v94)
            
            st.write("**Data Snippet (First 3 Rows):**")
            st.dataframe(df_v94.head(3))
        except Exception as e:
            st.error(f"Failed to load or parse: {e}")

    with col2:
        st.subheader("2. My Dry Run CGI-BIN URL")
        try:
            df_dry = pd.read_csv(URL_DRY_RUN, encoding='ISO-8859-1', on_bad_lines='skip')
            st.success("Download Successful")
            
            st.write("**Raw Column Names:**")
            st.write(df_dry.columns.tolist())
            
            st.write("**Cleaned Column Names (Lowercase/Stripped):**")
            clean_cols_dry = df_dry.columns.str.strip().str.lower().str.replace(' ', '_').tolist()
            st.write(clean_cols_dry)
            
            st.write("**Data Snippet (First 3 Rows):**")
            st.dataframe(df_dry.head(3))
        except Exception as e:
            st.error(f"Failed to load or parse: {e}")
