import streamlit as st
from pyemvue import PyEmVue
from pyemvue.enums import Scale, Unit
import datetime
import pandas as pd

# Configure page layout for responsiveness
st.set_page_config(
    page_title="Emporia Energy Dashboard", 
    page_icon="⚡", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Mobile-first CSS tweaks
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
st.write("Live electricity consumption and cost breakdown.")

# Hardcoded credentials
USERNAME = "kennyl41291@gmail.com"
PASSWORD = "19585723a"

# Cost calculation function: (usage * $0.44) + $30
def calculate_cost(kwh):
    return (kwh * 0.44) + 30.0

if st.button("🔄 Refresh Energy Data", type="primary", use_container_width=True):
    with st.spinner("Fetching live energy data..."):
        try:
            vue = PyEmVue()
            vue.login(username=USERNAME, password=PASSWORD)
            devices = vue.get_devices()

            now = datetime.datetime.now(datetime.timezone.utc)
            
            # 1. Current Month Range (Month-to-Date)
            curr_start = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
            curr_end = now
            curr_month_name = now.strftime('%B %Y')

            # 2. Previous Month Range (Full Month)
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

            # Fetch data for Previous Month
            prev_raw_data = []
            for item in devices_map:
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
                        "Property / Device": item["name"], 
                        "Usage (kWh)": round(total_usage, 2), 
                        "Estimated Cost ($)": round(est_cost, 2)
                    })
                except Exception:
                    prev_raw_data.append({
                        "Property / Device": item["name"], 
                        "Usage (kWh)": 0.0, 
                        "Estimated Cost ($)": 30.0
                    })

            # Organize UI into Tabs
            tab1, tab2 = st.tabs([f"📅 Current MTD", f"📅 Previous Month"])

            with tab1:
                st.subheader(f"{curr_month_name}")
                st.caption(f"Period: {curr_start.strftime('%m/%d/%Y')} - {curr_end.strftime('%m/%d/%Y')}")
                if curr_raw_data:
                    df_curr = pd.DataFrame(curr_raw_data)
                    total_curr_kwh = df_curr["Usage (kWh)"].sum()
                    total_curr_cost = df_curr["Estimated Cost ($)"].sum()
                    
                    st.metric(label="Total Portfolio Usage", value=f"{total_curr_kwh:,.2f} kWh")
                    st.metric(label="Total Portfolio Cost", value=f"${total_curr_cost:,.2f}")
                    
                    # Format table cells cleanly with units and currency signs as strings
                    df_curr["Usage (kWh)"] = df_curr["Usage (kWh)"].apply(lambda x: f"{x:,.2f}")
                    df_curr["Estimated Cost ($)"] = df_curr["Estimated Cost ($)"].apply(lambda x: f"${x:,.2f}")
                    
                    st.table(df_curr[['Property / Device', 'Usage (kWh)', 'Estimated Cost ($)']])
                else:
                    st.warning("No data found for current month.")

            with tab2:
                st.subheader(f"{prev_month_name}")
                display_end_date = prev_end - datetime.timedelta(days=1)
                st.caption(f"Period: {prev_start.strftime('%m/%d/%Y')} - {display_end_date.strftime('%m/%d/%Y')}")
                if prev_raw_data:
                    df_prev = pd.DataFrame(prev_raw_data)
                    total_prev_kwh = df_prev["Usage (kWh)"].sum()
                    total_prev_cost = df_prev["Estimated Cost ($)"].sum()
                    
                    st.metric(label="Total Portfolio Usage", value=f"{total_prev_kwh:,.2f} kWh")
                    st.metric(label="Total Portfolio Cost", value=f"${total_prev_cost:,.2f}")
                    
                    # Format table cells cleanly with units and currency signs as strings
                    df_prev["Usage (kWh)"] = df_prev["Usage (kWh)"].apply(lambda x: f"{x:,.2f}")
                    df_prev["Estimated Cost ($)"] = df_prev["Estimated Cost ($)"].apply(lambda x: f"${x:,.2f}")
                    
                    st.table(df_prev[['Property / Device', 'Usage (kWh)', 'Estimated Cost ($)']])
                else:
                    st.warning("No data found for previous month.")

        except Exception as e:
            st.error(f"Error: {e}")
