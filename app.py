import streamlit as st
from pyemvue import PyEmVue
from pyemvue.enums import Scale, Unit
import datetime
import pandas as pd
import urllib.parse
from streamlit_gsheets import GSheetsConnection

st.set_page_config(
    page_title="Emporia Energy Dashboard", 
    page_icon="⚡", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
    }
    .block-container {
        padding-top: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Emporia Dashboard")
st.write("Live electricity consumption, tenant SMS billing, and Google Sheets logging.")

# Hardcoded Emporia credentials
USERNAME = "kennyl41291@gmail.com"
PASSWORD = "19585723a"

# Cost calculation function: (usage * $0.44) + $30
def calculate_cost(kwh):
    return (kwh * 0.44) + 30.0

# Initialize Google Sheets connection
conn = st.connection("gsheets", type=GSheetsConnection)

# Helper function to load Tenant Directory from Google Sheets
def load_tenant_directory():
    try:
        df = conn.read(worksheet="TenantDirectory", ttl="10s")
        return df.fillna("")
    except Exception:
        return pd.DataFrame([
            {"Device Name": "1631 74th St Basement Rear", "Tenant": "Shaheer", "Phone": "2022904910"},
            {"Device Name": "1563 70th St Basement Front", "Tenant": "Francisco", "Phone": "9295498478"},
            {"Device Name": "1563 70th St 1F", "Tenant": "Marcos", "Phone": "9179821594"},
            {"Device Name": "6628 Wallaston 1F", "Tenant": "Edwin", "Phone": "9297052008"},
            {"Device Name": "1563 70th st 1Rear", "Tenant": "Angel", "Phone": "2016405388"},
            {"Device Name": "1563 70th st Basement Rear", "Tenant": "N/A", "Phone": ""}
        ])

# --- SIDEBAR TENANT MANAGEMENT ---
st.sidebar.header("📝 Manage Tenants")
st.sidebar.caption("Modifying tenant information here syncs directly with Google Sheets.")

current_tenants_df = load_tenant_directory()
edited_tenants_df = st.sidebar.data_editor(current_tenants_df, hide_index=True, num_rows="dynamic")

if not edited_tenants_df.equals(current_tenants_df):
    try:
        conn.update(worksheet="TenantDirectory", data=edited_tenants_df)
        st.sidebar.success("Updated Google Sheet successfully!")
    except Exception as e:
        st.sidebar.error(f"Failed to update Sheet: {e}")

TENANT_DIRECTORY = {}
for _, row in edited_tenants_df.iterrows():
    TENANT_DIRECTORY[str(row["Device Name"])] = {
        "name": str(row["Tenant"]),
        "phone": str(row["Phone"]).strip()
    }


if st.button("🔄 Refresh Energy Data", type="primary", use_container_width=True):
    with st.spinner("Fetching live energy data..."):
        try:
            vue = PyEmVue()
            vue.login(username=USERNAME, password=PASSWORD)
            devices = vue.get_devices()

            now = datetime.datetime.now(datetime.timezone.utc)
            
            # Current Month Range (MTD)
            curr_start = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
            curr_end = now
            curr_month_name = now.strftime('%B %Y')

            # Previous Month Range
            if now.month == 1:
                prev_start = datetime.datetime(now.year - 1, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
                prev_end = datetime.datetime(now.year, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
            else:
                prev_start = datetime.datetime(now.year, now.month - 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
                prev_end = curr_start
            
            prev_month_name = prev_start.strftime('%B %Y')

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

            # Fetch Current Month Data
            curr_raw_data = []
            for item in devices_map:
                dev_name = item["name"]
                t_info = TENANT_DIRECTORY.get(dev_name, {"name": "Unknown", "phone": ""})
                try:
                    usage_list, _ = vue.get_chart_usage(
                        channel=item["channel"],
                        start=curr_start,
                        end=curr_end,
                        scale=Scale.DAY.value,
                        unit=Unit.KWH.value
                    )
                    total_usage = sum(v for v in usage_list if v is not None) if usage_list else 0.0
                    est_cost = calculate_cost(total_usage)
                    curr_raw_data.append({
                        "Device Name": dev_name,
                        "Tenant": t_info["name"],
                        "Phone": t_info["phone"],
                        "Usage (kWh)": round(total_usage, 2), 
                        "Estimated Cost ($)": round(est_cost, 2)
                    })
                except Exception:
                    curr_raw_data.append({
                        "Device Name": dev_name,
                        "Tenant": t_info["name"],
                        "Phone": t_info["phone"],
                        "Usage (kWh)": 0.0, 
                        "Estimated Cost ($)": 30.0
                    })

            # Fetch Previous Month Data
            prev_raw_data = []
            for item in devices_map:
                dev_name = item["name"]
                t_info = TENANT_DIRECTORY.get(dev_name, {"name": "Unknown", "phone": ""})
                try:
                    usage_list, _ = vue.get_chart_usage(
                        channel=item["channel"],
                        start=prev_start,
                        end=prev_end,
                        scale=Scale.DAY.value,
                        unit=Unit.KWH.value
                    )
                    total_usage = sum(v for v in usage_list if v is not None) if usage_list else 0.0
                    est_cost = calculate_cost(total_usage)
                    prev_raw_data.append({
                        "Device Name": dev_name,
                        "Tenant": t_info["name"],
                        "Phone": t_info["phone"],
                        "Usage (kWh)": round(total_usage, 2), 
                        "Estimated Cost ($)": round(est_cost, 2)
                    })
                except Exception:
                    prev_raw_data.append({
                        "Device Name": dev_name,
                        "Tenant": t_info["name"],
                        "Phone": t_info["phone"],
                        "Usage (kWh)": 0.0, 
                        "Estimated Cost ($)": 30.0
                    })

            st.session_state["curr_data"] = curr_raw_data
            st.session_state["curr_month_name"] = curr_month_name
            st.session_state["prev_data"] = prev_raw_data
            st.session_state["prev_month_name"] = prev_month_name
            st.session_state["data_loaded"] = True

        except Exception as e:
            st.error(f"Error fetching data: {e}")

# Display Tabs if data is present
if st.session_state.get("data_loaded", False):
    tab1, tab2 = st.tabs(["📅 Current MTD", "📅 Previous Month"])

    with tab1:
        curr_month_name = st.session_state["curr_month_name"]
        curr_raw_data = st.session_state["curr_data"]
        df_curr = pd.DataFrame(curr_raw_data)
        
        st.subheader(f"{curr_month_name}")
        st.metric(label="Total Portfolio Usage", value=f"{df_curr['Usage (kWh)'].sum():,.2f} kWh")
        st.metric(label="Total Portfolio Cost", value=f"${df_curr['Estimated Cost ($)'].sum():,.2f}")
        
        # --- RECORD TO GOOGLE SHEET BUTTON (Newest at Top) ---
        if st.button("📝 Record Current Month to Google Sheet", use_container_width=True):
            try:
                existing_history = conn.read(worksheet="BillingHistory", ttl="0s").fillna("")
                now_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_records = []
                for _, r in df_curr.iterrows():
                    new_records.append({
                        "Timestamp": now_timestamp,
                        "Month/Year": curr_month_name,
                        "Device Name": r["Device Name"],
                        "Tenant": r["Tenant"],
                        "Phone": r["Phone"],
                        "Usage (kWh)": r["Usage (kWh)"],
                        "Estimated Cost ($)": r["Estimated Cost ($)"]
                    })
                
                # Place new records FIRST, pushing existing history down
                updated_history = pd.concat([pd.DataFrame(new_records), existing_history], ignore_index=True)
                conn.update(worksheet="BillingHistory", data=updated_history)
                st.success(f"Successfully recorded {len(new_records)} entries to the top of Google Sheet!")
            except Exception as ex:
                st.error(f"Failed to record data: {ex}")

        st.markdown("---")
        st.write("### 💬 Tenant SMS Quick-Send (Spanish)")
        
        for index, row in df_curr.iterrows():
            prop_name = row["Device Name"]
            tenant_name = row["Tenant"]
            phone_num = row["Phone"]
            usage = row["Usage (kWh)"]
            cost = row["Estimated Cost ($)"]
            
            msg = f"Hola! Su recibo de luz correspondiente a este mes es de ${cost:,.2f}."
            encoded_msg = urllib.parse.quote(msg)
            sms_link = f"sms:{phone_num}?body={encoded_msg}"
            
            col_info, col_btn = st.columns([2, 1])
            with col_info:
                st.text(f"{prop_name}\nTenant: {tenant_name} ({phone_num})\nUsage: {usage:,.2f} kWh | Due: ${cost:,.2f}")
            with col_btn:
                if phone_num and str(phone_num).lower() != "nan":
                    st.markdown(
                        f'<a href="{sms_link}"><button style="background-color:#007AFF; color:white; border:none; padding:8px 12px; border-radius:4px; font-weight:bold; cursor:pointer; width:100%;">Text 💬</button></a>',
                        unsafe_allow_html=True
                    )
                else:
                    st.text("No Phone")
            st.divider()

    with tab2:
        prev_month_name = st.session_state["prev_month_name"]
        prev_raw_data = st.session_state["prev_data"]
        df_prev = pd.DataFrame(prev_raw_data)
        
        st.subheader(f"{prev_month_name}")
        st.metric(label="Total Portfolio Usage", value=f"{df_prev['Usage (kWh)'].sum():,.2f} kWh")
        st.metric(label="Total Portfolio Cost", value=f"${df_prev['Estimated Cost ($)'].sum():,.2f}")
        
        # --- RECORD PREVIOUS MONTH BUTTON (Newest at Top) ---
        if st.button("📝 Record Previous Month to Google Sheet", use_container_width=True):
            try:
                existing_history = conn.read(worksheet="BillingHistory", ttl="0s").fillna("")
                now_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                new_records = []
                for _, r in df_prev.iterrows():
                    new_records.append({
                        "Timestamp": now_timestamp,
                        "Month/Year": prev_month_name,
                        "Device Name": r["Device Name"],
                        "Tenant": r["Tenant"],
                        "Phone": r["Phone"],
                        "Usage (kWh)": r["Usage (kWh)"],
                        "Estimated Cost ($)": r["Estimated Cost ($)"]
                    })
                
                # Place new records FIRST, pushing existing history down
                updated_history = pd.concat([pd.DataFrame(new_records), existing_history], ignore_index=True)
                conn.update(worksheet="BillingHistory", data=updated_history)
                st.success(f"Successfully recorded {len(new_records)} entries to the top of Google Sheet!")
            except Exception as ex:
                st.error(f"Failed to record data: {ex}")

        st.markdown("---")
        st.write("### 💬 Tenant SMS Quick-Send (Spanish)")
        
        for index, row in df_prev.iterrows():
            prop_name = row["Device Name"]
            tenant_name = row["Tenant"]
            phone_num = row["Phone"]
            usage = row["Usage (kWh)"]
            cost = row["Estimated Cost ($)"]
            
            msg = f"Hola! Su recibo de luz correspondiente al mes pasado es de ${cost:,.2f}."
            encoded_msg = urllib.parse.quote(msg)
            sms_link = f"sms:{phone_num}?body={encoded_msg}"
            
            col_info, col_btn = st.columns([2, 1])
            with col_info:
                st.text(f"{prop_name}\nTenant: {tenant_name} ({phone_num})\nUsage: {usage:,.2f} kWh | Due: ${cost:,.2f}")
            with col_btn:
                if phone_num and str(phone_num).lower() != "nan":
                    st.markdown(
                        f'<a href="{sms_link}"><button style="background-color:#007AFF; color:white; border:none; padding:8px 12px; border-radius:4px; font-weight:bold; cursor:pointer; width:100%;">Text 💬</button></a>',
                        unsafe_allow_html=True
                    )
                else:
                    st.text("No Phone")
            st.divider()
