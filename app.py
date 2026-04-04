import streamlit as st
import pandas as pd

# 1. Page Setup
st.set_page_config(page_title="Agency CRM", page_icon="🏛️", layout="wide")
st.title("Nonprofit Grant & Fundraising CRM 🏛️")

# 2. Function to load data directly from your CSV
@st.cache_data # This makes the app run super fast!
def load_data():
    # Read the CSV file you uploaded to GitHub
    df = pd.read_csv('agency_crm.csv')
    
    # Add our default CRM columns if they don't exist yet
    if 'app_status' not in df.columns:
        df['app_status'] = 'Not Started'
    if 'fundraising_active' not in df.columns:
        df['fundraising_active'] = 'No'
        
    # Make sure all data is text so our search doesn't crash
    df = df.astype(str)
    return df

# 3. Load the data
try:
    df = load_data()
except FileNotFoundError:
    st.error("⚠️ Cannot find 'agency_crm.csv'. Make sure it is uploaded to your GitHub repository!")
    st.stop()

# 4. The Search Bar
search_term = st.text_input("🔍 Search by Nonprofit Name, EIN, or Email:")

# 5. Filter and Display the Data
if search_term:
    # This checks every column for the search term
    mask = df.apply(lambda row: row.str.contains(search_term, case=False).any(), axis=1)
    filtered_df = df[mask]
else:
    filtered_df = df

st.write(f"**Found {len(filtered_df)} nonprofits:**")
st.dataframe(filtered_df, use_container_width=True)