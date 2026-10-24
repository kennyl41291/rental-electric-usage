import streamlit as st
import pandas as pd
import json
import os

TENANT_FILE = "tenants.json"

def load_local_tenants():
    if os.path.exists(TENANT_FILE):
        try:
            with open(TENANT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return [
        {"Device Name": "1631 74th St Basement Rear", "Tenant": "Shaheer", "Phone": "2022904910"},
        {"Device Name": "1563 70th St Basement Front", "Tenant": "Francisco", "Phone": "9295498478"},
        {"Device Name": "1563 70th St 1F", "Tenant": "Marcos", "Phone": "9179821594"},
        {"Device Name": "6628 Wallaston 1F", "Tenant": "Edwin", "Phone": "9297052008"},
        {"Device Name": "1563 70th st 1Rear", "Tenant": "Angel", "Phone": "2016405388"},
        {"Device Name": "1563 70th st Basement Rear", "Tenant": "N/A", "Phone": ""}
    ]

def save_local_tenants(data):
    with open(TENANT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

st.set_page_config(page_title="Rental Energy Dashboard", page_icon="⚡", layout="wide")

st.title("⚡ Rental Energy Dashboard")

# --- TABLE-BASED TENANT MANAGEMENT ---
with st.expander("📊 Manage Tenants (Interactive Table)", expanded=False):
    st.markdown("Click directly inside any cell to edit tenant names, phone numbers, or device names. Add or delete rows using the built-in table controls, then hit **Save Table Changes**.")
    
    raw_data = load_local_tenants()
    df = pd.DataFrame(raw_data)
    
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key="tenant_table_editor"
    )
    
    if st.button("💾 Save Table Changes", type="primary"):
        updated_data = edited_df.to_dict(orient="records")
        for item in updated_data:
            if "Phone" in item and item["Phone"] is not None:
                item["Phone"] = str(item["Phone"]).strip()
            if "Device Name" in item and item["Device Name"] is not None:
                item["Device Name"] = str(item["Device Name"]).strip()
            if "Tenant" in item and item["Tenant"] is not None:
                item["Tenant"] = str(item["Tenant"]).strip()
                
        save_local_tenants(updated_data)
        st.success("Tenant directory updated successfully!")
        st.rerun()

st.divider()

# --- DASHBOARD METRICS & CHARTS ---
st.subheader("📈 Energy Consumption Overview")
st.info("Your consumption charts, billing calculations, and historical logs display here.")
