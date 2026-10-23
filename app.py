import datetime
import os
import urllib.parse
import streamlit as st
import pandas as pd
from pyemvue import PyEmVue
from pyemvue.enums import Scale, Unit

# Page Config
st.set_page_config(page_title="Emporia Energy Dashboard", page_icon="⚡", layout="wide")

# Secrets / Environment Variables
USERNAME = os.environ.get("EMPORIA_USERNAME") or st.secrets.get("EMPORIA_USERNAME")
PASSWORD = os.environ.get("EMPORIA_PASSWORD") or st.secrets.get("EMPORIA_PASSWORD")

# Default Tenant Configuration
DEFAULT_TENANTS = [
    {"Device Name": "1631 74th St Basement Rear", "Tenant": "Shaheer", "Phone": "2022904910"},
    {"Device Name": "1563 70th St Basement Front", "Tenant": "Francisco", "Phone": "9295498478"},
    {"Device Name": "1563 70th St 1F", "Tenant": "Marcos", "Phone": "9179821594"},
    {"Device Name": "6628 Wallaston 1F", "Tenant": "Edwin", "Phone": "9297052008"},
    {"Device Name": "1563 70th st 1Rear", "Tenant": "Angel", "Phone": "2016405388"},
    {"Device Name": "1563 70th st Basement Rear", "Tenant": "N/A", "Phone": ""}
]

def calculate_cost(kwh):
    return (kwh * 0.44) + 30.0

def fetch_emporia_data(username, password):
    vue = PyEmVue()
    vue.login(username=username, password=password)
    devices = vue.get_devices()

    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Previous Month Range
    if now.month == 1:
        prev_start = datetime.datetime(now.year - 1, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        prev_end = datetime.datetime(now.year, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    else:
        prev_start = datetime.datetime(now.year, now.month - 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        prev_end = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)

    # Current Month Range
    curr_start = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
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
        prev_data.append({"Device Name": dev_name, "Usage (kWh)": round(tot_prev, 2), "Estimated Cost ($)": round(calculate_cost(tot_prev), 2)})

        # Fetch Current Month (MTD)
        try:
            usage_curr, _ = vue.get_chart_usage(item["channel"], start=curr_start, end=curr_end, scale=Scale.DAY.value, unit=Unit.KWH.value)
            tot_curr = sum(v for v in usage_curr if v is not None) if usage_curr else 0.0
        except Exception:
            tot_curr = 0.0
        curr_data.append({"Device Name": dev_name, "Usage (kWh)": round(tot_curr, 2), "Estimated Cost ($)": round(calculate_cost(tot_curr), 2)})

    prev_month_label = prev_start.strftime('%B %Y')
    curr_month_label = f"{curr_start.strftime('%B %Y')} (MTD)"

    return pd.DataFrame(prev_data), pd.DataFrame(curr_data), prev_month_label, curr_month_label

# Sidebar - Tenant Directory Management
st.sidebar.title("🏢 Tenant Directory")
if "tenant_df" not in st.session_state:
    st.session_state.tenant_df = pd.DataFrame(DEFAULT_TENANTS)

edited_tenant_df = st.sidebar.data_editor(
    st.session_state.tenant_df,
    num_rows="dynamic",
    key="tenant_editor"
)

# Main UI
st.title("⚡ Emporia Energy Usage Dashboard")

if not USERNAME or not PASSWORD:
    st.error("Please configure EMPORIA_USERNAME and EMPORIA_PASSWORD environment variables or secrets.")
else:
    if st.button("🔄 Fetch Latest Energy Data", type="primary"):
        with st.spinner("Connecting to Emporia..."):
            try:
                df_prev, df_curr, prev_label, curr_label = fetch_emporia_data(USERNAME, PASSWORD)
                st.session_state.df_prev = df_prev
                st.session_state.df_curr = df_curr
                st.session_state.prev_label = prev_label
                st.session_state.curr_label = curr_label
            except Exception as e:
                st.error(f"Failed to fetch Emporia data: {e}")

    if "df_prev" in st.session_state:
        df_prev = pd.merge(edited_tenant_df, st.session_state.df_prev, on="Device Name", how="left")
        df_curr = pd.merge(edited_tenant_df, st.session_state.df_curr, on="Device Name", how="left")

        tab1, tab2 = st.tabs([f"📅 Previous Month: {st.session_state.prev_label}", f"📊 Current Month: {st.session_state.curr_label}"])

        with tab1:
            st.subheader(f"Usage & Cost Breakdown for {st.session_state.prev_label}")
            col1, col2 = st.columns(2)
            col1.metric("Total Usage (kWh)", f"{df_prev['Usage (kWh)'].sum():,.2f} kWh")
            col2.metric("Total Estimated Cost", f"${df_prev['Estimated Cost ($)'].sum():,.2f}")
            
            st.dataframe(df_prev, use_container_width=True)

            # Tenant Text Links Section
            st.markdown("### 📱 Text Tenants (Previous Month)")
            for _, row in df_prev.iterrows():
                phone = str(row.get("Phone", "")).strip()
                tenant_name = row.get("Tenant", "Tenant")
                cost = row.get("Estimated Cost ($)", 0.0)
                usage = row.get("Usage (kWh)", 0.0)
                
                if phone and phone != "nan" and phone != "":
                    message = f"Hola {tenant_name}, tu factura de luz de {st.session_state.prev_label} es ${cost:.2f} ({usage} kWh). Gracias!"
                    encoded_msg = urllib.parse.quote(message)
                    sms_url = f"sms:{phone}?body={encoded_msg}"
                    st.markdown(f"💬 **{tenant_name}** ({phone}) — [📲 Send SMS Text]({sms_url})")

        with tab2:
            st.subheader(f"Month-to-Date Usage & Cost for {st.session_state.curr_label}")
            col1, col2 = st.columns(2)
            col1.metric("MTD Usage (kWh)", f"{df_curr['Usage (kWh)'].sum():,.2f} kWh")
            col2.metric("MTD Estimated Cost", f"${df_curr['Estimated Cost ($)'].sum():,.2f}")
            
            st.dataframe(df_curr, use_container_width=True)

            # MTD Tenant Text Links Section
            st.markdown("### 📱 Text Tenants (Current Month MTD)")
            for _, row in df_curr.iterrows():
                phone = str(row.get("Phone", "")).strip()
                tenant_name = row.get("Tenant", "Tenant")
                cost = row.get("Estimated Cost ($)", 0.0)
                usage = row.get("Usage (kWh)", 0.0)
                
                if phone and phone != "nan" and phone != "":
                    message = f"Hola {tenant_name}, tu uso actual de luz (MTD) es ${cost:.2f} ({usage} kWh)."
                    encoded_msg = urllib.parse.quote(message)
                    sms_url = f"sms:{phone}?body={encoded_msg}"
                    st.markdown(f"💬 **{tenant_name}** ({phone}) — [📲 Send SMS Text]({sms_url})")
