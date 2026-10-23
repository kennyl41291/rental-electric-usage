import streamlit as st
from pyemvue import PyEmVue
from pyemvue.enums import Scale, Unit
import datetime
import pandas as pd
import urllib.parse

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
    table {
        font-size: 13px !important;
        width: 100% !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Emporia Dashboard")
st.write("Live electricity consumption and tenant SMS billing.")

# Hardcoded credentials
USERNAME = "kennyl41291@gmail.com"
PASSWORD = "19585723a"

# Cost calculation function: (usage * $0.44) + $30
def calculate_cost(kwh):
    return (kwh * 0.44) + 30.0

# Map your Emporia device/property names to tenant phone numbers (include country code or dashes, e.g., "+15551234567")
TENANT_PHONE_NUMBERS = {
    "Device Name 1": "+15551234567",
    "Device Name 2": "+15559876543"
}

if st.button("🔄 Refresh Energy Data", type="primary", use_container_width=True):
    with st.spinner("Fetching live energy data..."):
        try:
            vue = PyEmVue()
            vue.login(username=USERNAME, password=PASSWORD)
            devices = vue.get_devices()

            now = datetime.datetime.now(datetime.timezone.utc)
            curr_start = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
            curr_end = now
            curr_month_name = now.strftime('%B %Y')

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

            # Fetch data for Current Month
            curr_raw_data = []
            for item in devices_map:
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
                        "Property / Device": item["name"], 
                        "Usage (kWh)": round(total_usage, 2), 
                        "Estimated Cost ($)": round(est_cost, 2)
                    })
                except Exception:
                    curr_raw_data.append({
                        "Property / Device": item["name"], 
                        "Usage (kWh)": 0.0, 
                        "Estimated Cost ($)": 30.0
                    })

            st.subheader(f"Current Month: {curr_month_name}")
            
            if curr_raw_data:
                df_curr = pd.DataFrame(curr_raw_data)
                total_curr_kwh = df_curr["Usage (kWh)"].sum()
                total_curr_cost = df_curr["Estimated Cost ($)"].sum()
                
                st.metric(label="Total Portfolio Usage", value=f"{total_curr_kwh:,.2f} kWh")
                st.metric(label="Total Portfolio Cost", value=f"${total_curr_cost:,.2f}")
                
                st.markdown("---")
                st.write("### 💬 Tenant SMS Quick-Send")
                
                # Loop through each property to create an individual SMS link button
                for index, row in df_curr.iterrows():
                    prop_name = row["Property / Device"]
                    usage = row["Usage (kWh)"]
                    cost = row["Estimated Cost ($)"]
                    
                    # Pre-write the friendly message
                    msg = (
                        f"Hi! Here is your electricity breakdown for {curr_month_name}:\n"
                        f"⚡ Usage: {usage:,.2f} kWh\n"
                        f"💵 Total Due: ${cost:,.2f}"
                    )
                    encoded_msg = urllib.parse.quote(msg)
                    
                    # Pull phone number if mapped, otherwise default empty string
                    phone = TENANT_PHONE_NUMBERS.get(prop_name, "")
                    
                    # Native SMS URI scheme (works universally on iOS and Android)
                    sms_link = f"sms:{phone}?body={encoded_msg}"
                    
                    # Render layout with a native text message button
                    col_info, col_btn = st.columns([2, 1])
                    with col_info:
                        st.text(f"{prop_name}\nCost: ${cost:,.2f} ({usage} kWh)")
                    with col_btn:
                        st.markdown(
                            f'<a href="{sms_link}"><button style="background-color:#007AFF; color:white; border:none; padding:8px 12px; border-radius:4px; font-weight:bold; cursor:pointer; width:100%;">Text 💬</button></a>',
                            unsafe_allow_html=True
                        )
                    st.divider()

        except Exception as e:
            st.error(f"Error: {e}")
