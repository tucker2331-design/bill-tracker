import streamlit as st
import re

st.set_page_config(page_title="Regex Test")
st.title("🧪 Regex Extraction Unit Test")
st.info("Testing Positive Extraction logic before putting it in the Ghost Worker.")

# 1. The Function We Are Testing
def parse_history_action(action_text):
    parent_comm = "-"
    sub_comm = "-"
    vote_count = "-"
    
    # Extract Vote Tally
    vote_match = re.search(r'\(\s*(\d+-Y\s+\d+-N.*?)\s*\)', action_text, re.IGNORECASE)
    if vote_match:
        vote_count = vote_match.group(1).strip()
        
    # Extract Subcommittee
    sub_match = re.search(r'(Subcommittee[^)]*)', action_text, re.IGNORECASE)
    if sub_match:
        sub_comm = sub_match.group(1).strip()
        
    # Extract Parent Committee (Basic extraction for the test)
    if "referred to" in action_text.lower():
        match = re.search(r'referred to\s?([a-z\s&,-]+)', action_text.lower())
        if match:
            raw_comm = match.group(1).split('(')[0].strip().title()
            parent_comm = "House " + raw_comm if action_text.startswith("H ") else "Senate " + raw_comm
            
    return parent_comm, sub_comm, vote_count

# 2. The Stress Test Data
test_strings = [
    "H Referred to Committee on Finance (Rasoul)",
    "H Reported from General Laws (Subcommittee #1) (Simon) (15-Y 7-N)",
    "S Passed Senate (21-Y 19-N)",
    "H Referred to Health, Welfare and Institutions (Subcommittee on Health)",
    "H Engrossed by House - committee substitute HB1H1"
]

# 3. The Execution
for text in test_strings:
    parent, sub, vote = parse_history_action(text)
    st.markdown(f"**RAW STRING:** `{text}`")
    st.markdown(f"👉 **PARENT:** {parent}")
    st.markdown(f"👉 **SUBCOMM:** {sub}")
    st.markdown(f"👉 **VOTE:** {vote}")
    st.divider()
