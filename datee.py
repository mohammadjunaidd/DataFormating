import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Odoo 19 Data Architect", layout="wide")

st.title("📑 Odoo 19 Dynamic Data Importer")
st.markdown("Clean, filter, and structure your data for Odoo One2Many imports.")

def show_preview(df, title):
    st.subheader(f"👀 Preview: {title}")
    st.dataframe(df.head(10), use_container_width=True)
    st.caption(f"Showing top 10 rows of {len(df)} total rows.")

uploaded_file = st.file_uploader("Upload Raw Data (CSV or Excel)", type=['csv', 'xlsx'])

if uploaded_file:
    # 1. LOAD DATA
    if "raw_df" not in st.session_state:
        if uploaded_file.name.endswith('.csv'):
            st.session_state.raw_df = pd.read_csv(uploaded_file)
        else:
            st.session_state.raw_df = pd.read_excel(uploaded_file)
    
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

        # 3. DATE PROCESSING (CONVERT -> FILTER -> FORMAT)
        st.header("Step 2: Date Processing")
        date_col = st.selectbox("Identify the Primary Date column:", ["None"] + selected_cols)
        
        if date_col != "None":
            # Convert to datetime object for logic
            df_filtered[date_col] = pd.to_datetime(df_filtered[date_col], errors='coerce')
            
            # Date Range Filter
            valid_dates = df_filtered[date_col].dropna()
            if not valid_dates.empty:
                min_d, max_d = valid_dates.min().date(), valid_dates.max().date()
                user_range = st.date_input("Select date range to keep:", [min_d, max_d])
                
                if len(user_range) == 2:
                    df_filtered = df_filtered[
                        (df_filtered[date_col].dt.date >= user_range[0]) & 
                        (df_filtered[date_col].dt.date <= user_range[1])
                    ]
            
            # Format for Export
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
            
            # Apply formatting (convert to string for the Excel export)
            df_filtered[date_col] = df_filtered[date_col].dt.strftime(format_map[date_format_choice])
            show_preview(df_filtered, f"After Date Filtering & Formatting ({date_format_choice})")

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
                # Group
                processed_df = df_filtered.groupby(group_by_cols, as_index=False).agg(agg_dict)
                
                # Explode
                list_cols = [col for col, action in agg_dict.items() if callable(action)]
                if list_cols:
                    processed_df = processed_df.explode(list_cols)
                
                # Masking logic
                header_cols = [col for col, action in agg_dict.items() if not callable(action)]
                
                def apply_odoo_mask(group):
                    cols_to_mask = group_by_cols + header_cols
                    for col in cols_to_mask:
                        # Keep value on row 0, set others to None/Empty string
                        if len(group) > 1:
                            group.iloc[1:, group.columns.get_loc(col)] = ""
                    return group

                final_output = processed_df.groupby(group_by_cols, sort=False, group_keys=False).apply(apply_odoo_mask)
                
                st.session_state.final_df = final_output
                st.success("Data successfully structured!")

        # 5. FINAL PREVIEW AND DOWNLOAD
        if "final_df" in st.session_state:
            final_df = st.session_state.final_df
            show_preview(final_df, "Final Odoo-Ready Output")
            
            output = BytesIO()
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