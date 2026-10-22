import streamlit as st
from pyemvue import PyEmVue
from pyemvue.enums import Scale, Unit
import datetime

st.set_page_config(page_title="Emporia Energy Dashboard", page_icon="⚡", layout="centered")

st.title("⚡ Emporia Energy - Current Month Dashboard")
st.write("Live electricity consumption report for your properties.")

# Sidebar credentials
st.sidebar.header("Account Credentials")
username = st.sidebar.text_input("Email", value="kennyl41291@gmail.com")
password = st.sidebar.text_input("Password", type="password", value="19585723a")

if st.button("🔄 Refresh Energy Data", type="primary"):
    with st.spinner("Connecting to Emporia & calculating usage..."):
        try:
            vue = PyEmVue()
            vue.login(username=username, password=password)
            devices = vue.get_devices()

            now = datetime.datetime.now(datetime.timezone.utc)
            start_time = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
            end_time = now
            month_name = now.strftime('%B %Y')

            st.subheader(f"📊 Report for {month_name}")
            st.caption(f"Period: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
            st.markdown("---")

            processed_gids = set()
            results = []

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
                    try:
                        usage_list, _ = vue.get_chart_usage(
                            channel=channel,
                            start=start_time,
                            end=end_time,
                            scale=Scale.DAY.value,
                            unit=Unit.KWH.value
                        )
                        
                        total_usage = sum(v for v in usage_list if v is not None) if usage_list else 0.0
                        results.append({"Property / Device": d_name, "Usage (kWh)": round(total_usage, 2)})
                        processed_gids.add(gid)
                        break
                    except Exception:
                        pass

            if results:
                total_portfolio = sum(r["Usage (kWh)"] for r in results)
                st.metric(label="Total Portfolio Consumption", value=f"{total_portfolio:,.2f} kWh")
                st.dataframe(results, use_container_width=True)
            else:
                st.warning("No usage data found.")

        except Exception as e:
            st.error(f"Error: {e}")