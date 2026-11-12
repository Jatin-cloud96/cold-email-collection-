import os
import sys
import io
import time
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

# Add current dir to path
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.append(str(CURRENT_DIR))

import config
from quota_manager import QuotaManager
from excel_manager import ExcelManager
from lead_finder import LeadFinderWorkflow

# Streamlit Page Setup
st.set_page_config(
    page_title="India Professional Email Lead Finder",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1F497D;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #F8F9FA;
        border: 1px solid #E9ECEF;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .badge-valid {
        background-color: #E8F5E9;
        color: #2E7D32;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Managers
quota_mgr = QuotaManager()
excel_mgr = ExcelManager()

# Header
st.markdown('<div class="main-header">💼 India Professional Email Lead Finder</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Automated verification of work emails for Analysts, Consultants & Project Managers in India</div>', unsafe_allow_html=True)

# Top Metrics Row
def load_excel_data() -> pd.DataFrame:
    if config.EXCEL_OUTPUT_PATH.exists():
        try:
            return pd.read_excel(config.EXCEL_OUTPUT_PATH)
        except Exception:
            pass
    return pd.DataFrame(columns=[
        "Name", "Title", "Company", "Domain", "Email", "Verification status", "Source", "Date found"
    ])

df_leads = load_excel_data()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Total Leads in Sheet", value=len(df_leads))
with col2:
    valid_count = len(df_leads[df_leads["Verification status"] == "valid"]) if not df_leads.empty else 0
    st.metric(label="Verified Valid Emails", value=valid_count)
with col3:
    google_rem = quota_mgr.get_remaining("google_search")
    st.metric(label="Google Free Quota Left", value=f"{google_rem}/50")
with col4:
    batch_rem = quota_mgr.get_remaining("batch_processed")
    st.metric(label="Today's Batch Quota Left", value=f"{batch_rem}/{config.DEFAULT_BATCH_SIZE}")

st.divider()

# Sidebar: Configuration
with st.sidebar:
    st.header("⚙️ Search Configuration")
    
    # Target Titles
    default_titles = ["Analyst", "Consultant", "Project Manager"]
    titles_selected = st.multiselect(
        "Target Titles",
        options=["Analyst", "Consultant", "Project Manager", "Senior Analyst", "Senior Consultant", "Scrum Master", "Product Manager", "Management Consultant"],
        default=default_titles
    )
    custom_title = st.text_input("Or add custom title:")
    if custom_title and custom_title not in titles_selected:
        titles_selected.append(custom_title)

    # Location
    location = st.text_input("Target Location", value="India", help="E.g., India, Mumbai, Bengaluru, Delhi NCR, Hyderabad")

    # Batch Size
    batch_size = st.slider("Batch Size per Run", min_value=5, max_value=30, value=15, step=5)

    # Verification Mode
    allow_risky = st.checkbox("Include Catch-All / Risky Emails", value=False, help="By default, only strict 100% deliverable emails are kept")

    st.subheader("Discovery Source")
    source_choice = st.radio(
        "Select People Finder Method:",
        options=["Google Programmable Search (Free)", "Direct LinkedIn Browser Search", "Upload LinkedIn Connections CSV"],
        index=0
    )

    csv_file_path = None
    use_linkedin = False

    if source_choice == "Direct LinkedIn Browser Search":
        use_linkedin = True
        st.info("Uses local Chrome session to search live LinkedIn profiles in India.")
        headless = st.checkbox("Run browser in background (headless)", value=True)
    elif source_choice == "Upload LinkedIn Connections CSV":
        uploaded_csv = st.file_uploader("Upload Connections.csv from LinkedIn Data Export", type=["csv"])
        if uploaded_csv:
            temp_csv_path = config.CACHE_DIR / "uploaded_connections.csv"
            with open(temp_csv_path, "wb") as f:
                f.write(uploaded_csv.getbuffer())
            csv_file_path = str(temp_csv_path)
            st.success("CSV Uploaded successfully!")
    else:
        headless = False

    st.divider()
    
    # Run Button
    run_clicked = st.button("🚀 Start Lead Finder Run", type="primary", use_container_width=True)

# Main Area: Run Execution or View Leads
if run_clicked:
    if not titles_selected:
        st.error("Please select at least one target title.")
    else:
        progress_bar = st.progress(0, text="Initializing workflow...")
        log_expander = st.expander("Live Run Logs", expanded=True)
        log_placeholder = log_expander.empty()
        
        logs = []
        def log_cb(msg: str):
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
            log_placeholder.code("\n".join(logs[-15:]))

        log_cb(f"Starting search for {titles_selected} in {location} (Batch: {batch_size})...")
        progress_bar.progress(20, text="Collecting candidate profiles...")

        workflow = LeadFinderWorkflow(
            batch_size=batch_size,
            strict_valid_only=not allow_risky
        )

        try:
            with st.spinner("Finding leads and verifying emails..."):
                found_count = workflow.run(
                    titles=titles_selected,
                    location=location,
                    csv_path=csv_file_path,
                    use_linkedin=use_linkedin,
                    headless=headless if use_linkedin else False
                )
            
            progress_bar.progress(100, text="Run Completed!")
            st.success(f"Run finished! Added {found_count} new verified leads.")
            time.sleep(1)
            st.rerun()

        except Exception as e:
            st.error(f"Error during run: {e}")
            progress_bar.progress(100, text="Run Error")

# Leads Table Viewer
st.subheader("📋 Saved Verified Leads")

df_leads = load_excel_data()

if df_leads.empty:
    st.info("No leads generated yet. Configure options in the sidebar and click 'Start Lead Finder Run'.")
else:
    # Filter Controls
    filter_col1, filter_col2, filter_col3 = st.columns([2, 1, 1])
    with filter_col1:
        search_query = st.text_input("🔍 Search Leads", placeholder="Search by name, company, domain, or title...")
    with filter_col2:
        status_filter = st.selectbox("Status Filter", ["All", "valid", "catch-all", "risky"])
    with filter_col3:
        st.write("") # spacing
        st.write("")
        # Download Excel Button
        if config.EXCEL_OUTPUT_PATH.exists():
            with open(config.EXCEL_OUTPUT_PATH, "rb") as f:
                excel_bytes = f.read()
            st.download_button(
                label="📥 Download Excel (.xlsx)",
                data=excel_bytes,
                file_name="india_leads.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # Apply Filters
    filtered_df = df_leads.copy()
    if search_query:
        mask = filtered_df.astype(str).apply(lambda row: row.str.contains(search_query, case=False).any(), axis=1)
        filtered_df = filtered_df[mask]
    if status_filter != "All":
        filtered_df = filtered_df[filtered_df["Verification status"] == status_filter]

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "Title": st.column_config.TextColumn("Job Title", width="large"),
            "Company": st.column_config.TextColumn("Company", width="medium"),
            "Domain": st.column_config.TextColumn("Domain", width="small"),
            "Email": st.column_config.TextColumn("Email Address", width="large"),
            "Verification status": st.column_config.TextColumn("Status", width="small"),
            "Source": st.column_config.TextColumn("Source", width="small"),
            "Date found": st.column_config.TextColumn("Date Found", width="small"),
        }
    )

    st.caption(f"Showing {len(filtered_df)} of {len(df_leads)} total leads.")
