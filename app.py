import datetime
import os
import json
import math
import urllib.parse
import zoneinfo
import streamlit as st
import pandas as pd
from pyemvue import PyEmVue
from pyemvue.enums import Scale, Unit

# Page Config
st.set_page_config(page_title="Emporia Energy Dashboard", page_icon="⚡", layout="wide")

# Secrets / Environment Variables
USERNAME = os.environ.get("EMPORIA_USERNAME") or st.secrets.get("EMPORIA_USERNAME")
PASSWORD = os.environ.get("EMPORIA_PASSWORD") or st.secrets.get("EMPORIA_PASSWORD")

TENANT_FILE = "tenants.json"

# Default Tenant Configuration
DEFAULT_TENANTS = [
    {"Device Name": "1631 74th St Basement Rear", "Tenant": "Shaheer", "Phone": "2022904910"},
    {"Device Name": "1563 70th St Basement Front", "Tenant": "Francisco", "Phone": "9295498478"},
    {"Device Name": "1563 70th St 1F", "Tenant": "Marcos", "Phone": "9179821594"},
    {"Device Name": "6628 Wallaston 1F", "Tenant": "Edwin", "Phone": "9297052008"},
    {"Device Name": "1563 70th st 1Rear", "Tenant": "Angel", "Phone": "2016405388"},
    {"Device Name": "1563 70th st Basement Rear", "Tenant": "N/A", "Phone": ""}
]

def load_tenants():
    if os.path.exists(TENANT_FILE):
        try:
            return pd.read_json(TENANT_FILE)
        except Exception:
            pass
    return pd.DataFrame(DEFAULT_TENANTS)

def save_tenants(df):
    df.to_json(TENANT_FILE, orient="records", indent=4)

def calculate_cost(kwh):
    raw_cost = (kwh * 0.44) + 30.0
    return math.ceil(raw_cost)  # Rounds up to the nearest whole dollar

@st.cache_data(ttl=600)
def fetch_emporia_data(username, password):
    vue = PyEmVue()
    vue.login(username=username, password=password)
    devices = vue.get_devices()

    # Use EST Timezone
    est_tz = zoneinfo.ZoneInfo("America/New_York")
    now = datetime.datetime.now(est_tz)
    
    # Previous Month Range (EST)
    if now.month == 1:
        prev_start = datetime.datetime(now.year - 1, 12, 1, 0, 0, 0, tzinfo=est_tz)
        prev_end = datetime.datetime(now.year, 1, 1, 0, 0, 0, tzinfo=est_tz)
    else:
        prev_start = datetime.datetime(now.year, now.month - 1, 1, 0, 0, 0, tzinfo=est_tz)
        prev_end = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=est_tz)

    # Current Month Range (EST MTD)
    curr_start = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=est_tz)
    curr_end = now

    processed_gids = set()
    devices_map = []

    for device in devices:
        gid = device.device_gid
        if gid in processed_gids:
            continue
        vue.populate_device_properties(device)
        d_name = getattr(device, 'device_name', None) or f"Device {gid}"
        channels = getattr(device, 'channels', [])
        main_channels = [c for c in channels if c.channel_num and (',' in str(c.channel_num) or str(c.channel_num) in ['1,2,3', 'Main'])]
        if not main_channels and channels:
            main_channels = [channels[0]]
        for channel in main_channels:
            devices_map.append({"gid": gid, "name": d_name, "channel": channel})
            processed_gids.add(gid)
            break

    prev_data = []
    curr_data = []

    for item in devices_map:
        dev_name = item["name"]
        
        # Fetch Prev Month
        try:
            usage_prev, _ = vue.get_chart_usage(item["channel"], start=prev_start, end=prev_end, scale=Scale.DAY.value, unit=Unit.KWH.value)
            tot_prev = sum(v for v in usage_prev if v is not None) if usage_prev else 0.0
        except Exception:
            tot_prev = 0.0
        prev_data.append({"Device Name": dev_name, "Usage (kWh)": round(tot_prev, 2), "Estimated Cost ($)": calculate_cost(tot_prev)})

        # Fetch Current Month (MTD)
        try:
            usage_curr, _ = vue.get_chart_usage(item["channel"], start=curr_start, end=curr_end, scale=Scale.DAY.value, unit=Unit.KWH.value)
            tot_curr = sum(v for v in usage_curr if v is not None) if usage_curr else 0.0
        except Exception:
            tot_curr = 0.0
        curr_data.append({"Device Name": dev_name, "Usage (kWh)": round(tot_curr, 2), "Estimated Cost ($)": calculate_cost(tot_curr)})

    prev_month_label = prev_start.strftime('%B %Y')
    curr_month_label = f"{curr_start.strftime('%B %Y')} (MTD)"

    return pd.DataFrame(prev_data), pd.DataFrame(curr_data), prev_month_label, curr_month_label

# Sidebar - Tenant Directory Management with Persistence
st.sidebar.title("🏢 Tenant Directory")
if "tenant_df" not in st.session_state:
    st.session_state.tenant_df = load_tenants()

edited_tenant_df = st.sidebar.data_editor(
    st.session_state.tenant_df,
    num_rows="dynamic",
    key="tenant_editor"
)

# Automatically save when changes are made in the sidebar editor
if not edited_tenant_df.equals(st.session_state.tenant_df):
    st.session_state.tenant_df = edited_tenant_df
    save_tenants(edited_tenant_df)

# Main UI
st.title("⚡ Emporia Energy Usage Dashboard")

if not USERNAME or not PASSWORD:
    st.error("Please configure EMPORIA_USERNAME and EMPORIA_PASSWORD environment variables or secrets.")
else:
    if "df_curr" not in st.session_state:
        try:
            df_prev, df_curr, prev_label, curr_label = fetch_emporia_data(USERNAME, PASSWORD)
            st.session_state.df_prev = df_prev
            st.session_state.df_curr = df_curr
            st.session_state.prev_label = prev_label
            st.session_state.curr_label = curr_label
        except Exception as e:
            st.error(f"Failed to fetch Emporia data automatically: {e}")

    if st.button("🔄 Refresh Energy Data", type="primary"):
        with st.spinner("Connecting to Emporia..."):
            try:
                df_prev, df_curr, prev_label, curr_label = fetch_emporia_data(USERNAME, PASSWORD)
                st.session_state.df_prev = df_prev
                st.session_state.df_curr = df_curr
                st.session_state.prev_label = prev_label
                st.session_state.curr_label = curr_label
                st.success("Data refreshed successfully!")
            except Exception as e:
                st.error(f"Failed to fetch Emporia data: {e}")

    if "df_curr" in st.session_state:
        df_prev = pd.merge(edited_tenant_df, st.session_state.df_prev, on="Device Name", how="left")
        df_curr = pd.merge(edited_tenant_df, st.session_state.df_curr, on="Device Name", how="left")

        # Tabs: Current Month first
        tab1, tab2 = st.tabs([f"📊 Current Month: {st.session_state.curr_label}", f"📅 Previous Month: {st.session_state.prev_label}"])

        with tab1:
            st.subheader(f"Month-to-Date Usage & Cost for {st.session_state.curr_label}")
            col1, col2 = st.columns(2)
            col1.metric("MTD Usage (kWh)", f"{df_curr['Usage (kWh)'].sum():,.2f} kWh")
            col2.metric("MTD Estimated Cost", f"${df_curr['Estimated Cost ($)'].sum():,.0f}")
            
            # --- Quick-Text Panel for Mobile ---
            st.markdown("### 📱 Quick-Text Tenants (Current Month)")
            for _, row in df_curr.iterrows():
                phone = str(row.get("Phone", "")).strip()
                tenant_name = row.get("Tenant", "Tenant")
                cost = row.get("Estimated Cost ($)", 0)
                usage = row.get("Usage (kWh)", 0.0)
                if phone and phone != "nan" and phone != "":
                    msg = f"Hola {tenant_name}, tu uso actual de luz (MTD) es ${cost} ({usage} kWh)."
                    sms_url = f"sms:{phone}?body={urllib.parse.quote(msg)}"
                    st.markdown(f"🔹 **{tenant_name}** (${cost}) → [💬 Send SMS Text]({sms_url})")
            st.markdown("---")

            st.dataframe(
                df_curr,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Estimated Cost ($)": st.column_config.NumberColumn(format="$%d")
                }
            )

        with tab2:
            st.subheader(f"Usage & Cost Breakdown for {st.session_state.prev_label}")
            col1, col2 = st.columns(2)
            col1.metric("Total Usage (kWh)", f"{df_prev['Usage (kWh)'].sum():,.2f} kWh")
            col2.metric("Total Estimated Cost", f"${df_prev['Estimated Cost ($)'].sum():,.0f}")
            
            # --- Quick-Text Panel for Mobile ---
            st.markdown("### 📱 Quick-Text Tenants (Previous Month)")
            for _, row in df_prev.iterrows():
                phone = str(row.get("Phone", "")).strip()
                tenant_name = row.get("Tenant", "Tenant")
                cost = row.get("Estimated Cost ($)", 0)
                usage = row.get("Usage (kWh)", 0.0)
                if phone and phone != "nan" and phone != "":
                    msg = f"Hola {tenant_name}, tu factura de luz de {st.session_state.prev_label} es ${cost} ({usage} kWh). Gracias!"
                    sms_url = f"sms:{phone}?body={urllib.parse.quote(msg)}"
                    st.markdown(f"🔹 **{tenant_name}** (${cost}) → [💬 Send SMS Text]({sms_url})")
            st.markdown("---")

            st.dataframe(
                df_prev,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Estimated Cost ($)": st.column_config.NumberColumn(format="$%d")
                }
            )
