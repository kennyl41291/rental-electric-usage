import streamlit as st
from pyemvue import PyEmVue
from pyemvue.enums import Scale, Unit
import datetime

st.set_page_config(page_title="Emporia Energy Dashboard", page_icon="⚡", layout="centered")

st.title("⚡ Emporia Energy Dashboard")
st.write("Live electricity consumption report and cost breakdown for your properties.")

# Hardcoded credentials
USERNAME = "kennyl41291@gmail.com"
PASSWORD = "19585723a"

# Cost calculation function: (usage * $0.44) + $30
def calculate_cost(kwh):
    return round((kwh * 0.44) + 30.0, 2)

if st.button("🔄 Refresh Energy Data", type="primary"):
    with st.spinner("Connecting to Emporia & calculating usage and costs..."):
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
            curr_results = []
            for item in devices_map:
                try:
                    usage_list, _ = vue.get_chart_usage(
                        channel=item["channel"],
                        start=curr_start,
                        end=curr_end,
                        scale=Scale.DAY.value,
                        unit=Unit.KWH.value
                    )
                    total_usage = round(sum(v for v in usage_list if v is not None) if usage_list else 0.0, 2)
                    est_cost = calculate_cost(total_usage)
                    curr_results.append({
                        "Property / Device": item["name"], 
                        "Usage (kWh)": total_usage, 
                        "Estimated Cost ($)": est_cost
                    })
                except Exception:
                    curr_results.append({
                        "Property / Device": item["name"], 
                        "Usage (kWh)": 0.0, 
                        "Estimated Cost ($)": 30.0
                    })

            # Fetch data for Previous Month
            prev_results = []
            for item in devices_map:
                try:
                    usage_list, _ = vue.get_chart_usage(
                        channel=item["channel"],
                        start=prev_start,
                        end=prev_end,
                        scale=Scale.DAY.value,
                        unit=Unit.KWH.value
                    )
                    total_usage = round(sum(v for v in usage_list if v is not None) if usage_list else 0.0, 2)
                    est_cost = calculate_cost(total_usage)
                    prev_results.append({
                        "Property / Device": item["name"], 
                        "Usage (kWh)": total_usage, 
                        "Estimated Cost ($)": est_cost
                    })
                except Exception:
                    prev_results.append({
                        "Property / Device": item["name"], 
                        "Usage (kWh)": 0.0, 
                        "Estimated Cost ($)": 30.0
                    })

            # Organize UI into Tabs
            tab1, tab2 = st.tabs([f"📅 Current MTD ({curr_month_name})", f"📅 Previous Month ({prev_month_name})"])

            with tab1:
                st.subheader(f"Current Month-to-Date: {curr_month_name}")
                st.caption(f"Period: {curr_start.strftime('%Y-%m-%d')} to {curr_end.strftime('%Y-%m-%d')}")
                if curr_results:
                    total_curr_kwh = sum(r["Usage (kWh)"] for r in curr_results)
                    total_curr_cost = sum(r["Estimated Cost ($)"] for r in curr_results)
                    
                    col1, col2 = st.columns(2)
                    col1.metric(label="Total Portfolio Usage", value=f"{total_curr_kwh:,.2f} kWh")
                    col2.metric(label="Total Portfolio Cost", value=f"${total_curr_cost:,.2f}")
                    
                    st.dataframe(curr_results, use_container_width=True)
                else:
                    st.warning("No data found for current month.")

            with tab2:
                st.subheader(f"Previous Full Month: {prev_month_name}")
                display_end_date = prev_end - datetime.timedelta(days=1)
                st.caption(f"Period: {prev_start.strftime('%Y-%m-%d')} to {display_end_date.strftime('%Y-%m-%d')}")
                if prev_results:
                    total_prev_kwh = sum(r["Usage (kWh)"] for r in prev_results)
                    total_prev_cost = sum(r["Estimated Cost ($)"] for r in prev_results)
                    
                    col1, col2 = st.columns(2)
                    col1.metric(label="Total Portfolio Usage", value=f"{total_prev_kwh:,.2f} kWh")
                    col2.metric(label="Total Portfolio Cost", value=f"${total_prev_cost:,.2f}")
                    
                    st.dataframe(prev_results, use_container_width=True)
                else:
                    st.warning("No data found for previous month.")

        except Exception as e:
            st.error(f"Error: {e}")
