import streamlit as st
import pandas as pd
from io import BytesIO
 
# --- CONFIGURATION ---
st.set_page_config(page_title="Odoo 19 Data Architect", layout="wide")
 
# --- UI HEADER ---
st.title("📑 Odoo 19 Dynamic Data Importer")
st.markdown("Clean, filter, and structure your data for Odoo One2Many imports.")
 
# --- SIDEBAR RESET ---
with st.sidebar:
    st.header("⚙️ Settings")
    if st.button("🔄 Reset App & Clear Cache"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.info("Use this if you want to start a completely new session.")
 
# --- HELPER FUNCTIONS ---
def show_preview(df, title):
    st.subheader(f"👀 Preview: {title}")
    st.dataframe(df.head(10), use_container_width=True)
    st.caption(f"Showing top 10 rows of {len(df)} total rows.")
 
# --- FILE UPLOADER ---
uploaded_file = st.file_uploader("Upload Raw Data (CSV or Excel)", type=['csv', 'xlsx'])
 
if uploaded_file:
    # 1. SMART LOAD DATA (Detects if file changed)
    if "current_filename" not in st.session_state or st.session_state.current_filename != uploaded_file.name:
        if uploaded_file.name.endswith('.csv'):
            st.session_state.raw_df = pd.read_csv(uploaded_file)
        else:
            # Requires 'openpyxl' in requirements.txt
            st.session_state.raw_df = pd.read_excel(uploaded_file)
        st.session_state.current_filename = uploaded_file.name
        # Clear any old results from previous files
        if "final_df" in st.session_state:
            del st.session_state.final_df
    df_input = st.session_state.raw_df.copy()
    show_preview(df_input, "Original Data")
 
    # 2. COLUMN SELECTION
    st.header("Step 1: Column Selection")
    all_cols = df_input.columns.tolist()
    col_select_1, _ = st.columns([1, 4])
    with col_select_1:
        select_all = st.checkbox("Select All Columns", value=True)
    selected_cols = st.multiselect(
        "Columns to keep:",
        all_cols,
        default=all_cols if select_all else []
    )
    if selected_cols:
        df_filtered = df_input[selected_cols].copy()
        show_preview(df_filtered, "After Column Selection")
 
        # 3. DATE PROCESSING
        st.header("Step 2: Date Processing")
        date_col = st.selectbox("Identify the Primary Date column:", ["None"] + selected_cols)
        if date_col != "None":
            df_filtered[date_col] = pd.to_datetime(df_filtered[date_col], errors='coerce')
            valid_dates = df_filtered[date_col].dropna()
            if not valid_dates.empty:
                min_d, max_d = valid_dates.min().date(), valid_dates.max().date()
                user_range = st.date_input("Select date range to keep:", [min_d, max_d])
                if len(user_range) == 2:
                    df_filtered = df_filtered[
                        (df_filtered[date_col].dt.date >= user_range[0]) &
                        (df_filtered[date_col].dt.date <= user_range[1])
                    ]
            date_format_choice = st.radio(
                "Select Export Date Format:",
                ["YYYY-MM-DD (Odoo Standard)", "MM-DD-YYYY", "DD-MM-YYYY"],
                horizontal=True
            )
            format_map = {
                "YYYY-MM-DD (Odoo Standard)": "%Y-%m-%d",
                "MM-DD-YYYY": "%m-%d-%Y",
                "DD-MM-YYYY": "%d-%m-%Y"
            }
            df_filtered[date_col] = df_filtered[date_col].dt.strftime(format_map[date_format_choice])
            show_preview(df_filtered, f"After Date Filtering & Formatting")
 
        # 4. DYNAMIC GROUPING & ODOO MASKING
        st.header("Step 3: Grouping & Aggregation")
        group_by_cols = st.multiselect("Select the Unique ID to Group By (e.g., SO Number):", selected_cols)
        if group_by_cols:
            other_cols = [c for c in selected_cols if c not in group_by_cols]
            agg_dict = {}
 
            st.markdown("### Define Actions for Remaining Columns")
            cols_per_row = 3
            for i in range(0, len(other_cols), cols_per_row):
                ui_cols = st.columns(cols_per_row)
                for j, col in enumerate(other_cols[i:i + cols_per_row]):
                    with ui_cols[j]:
                        choice = st.selectbox(
                            f"Action for: {col}",
                            ["First Row", "Keep All Rows", "Sum", "Count Unique"],
                            key=f"agg_{col}"
                        )
                        if choice == "Keep All Rows":
                            agg_dict[col] = lambda x: list(x)
                        elif choice == "Sum":
                            agg_dict[col] = "sum"
                        elif choice == "Count Unique":
                            agg_dict[col] = "nunique"
                        else:
                            agg_dict[col] = "first"
 
            if st.button("🚀 Process & Structure Data"):
                # Grouping logic
                processed_df = df_filtered.groupby(group_by_cols, as_index=False).agg(agg_dict)
                # Explode columns that chose "Keep All Rows"
                list_cols = [col for col, action in agg_dict.items() if callable(action)]
                if list_cols:
                    processed_df = processed_df.explode(list_cols)
                # Masking logic for Odoo One2Many Imports
                header_cols = [col for col, action in agg_dict.items() if not callable(action)]
                def apply_odoo_mask(group):
                    cols_to_mask = group_by_cols + header_cols
                    if len(group) > 1:
                        # Keep value on first row, set others to empty
                        group.iloc[1:, [group.columns.get_loc(c) for c in cols_to_mask]] = ""
                    return group
 
                final_output = processed_df.groupby(group_by_cols, sort=False, group_keys=False).apply(apply_odoo_mask)
                st.session_state.final_df = final_output
                st.success("Data successfully structured!")
 
        # 5. FINAL PREVIEW AND DOWNLOAD
        if "final_df" in st.session_state:
            final_df = st.session_state.final_df
            show_preview(final_df, "Final Odoo-Ready Output")
            output = BytesIO()
            # Requires 'xlsxwriter' in requirements.txt
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False)
            st.download_button(
                label="📥 Download Structured Excel",
                data=output.getvalue(),
                file_name="odoo19_ready_import.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("Upload a file to begin.")
