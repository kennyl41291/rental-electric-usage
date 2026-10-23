import datetime
import os
import requests
from pyemvue import PyEmVue
from pyemvue.enums import Scale, Unit

USERNAME = os.environ.get("EMPORIA_USERNAME")
PASSWORD = os.environ.get("EMPORIA_PASSWORD")
GOOGLE_SCRIPT_URL = os.environ.get("GOOGLE_SCRIPT_URL")

# Tenant directory configuration
TENANTS = [
    {"Device Name": "1631 74th St Basement Rear", "Tenant": "Shaheer", "Phone": "2022904910"},
    {"Device Name": "1563 70th St Basement Front", "Tenant": "Francisco", "Phone": "9295498478"},
    {"Device Name": "1563 70th St 1F", "Tenant": "Marcos", "Phone": "9179821594"},
    {"Device Name": "6628 Wallaston 1F", "Tenant": "Edwin", "Phone": "9297052008"},
    {"Device Name": "1563 70th st 1Rear", "Tenant": "Angel", "Phone": "2016405388"},
    {"Device Name": "1563 70th st Basement Rear", "Tenant": "N/A", "Phone": ""}
]

TENANT_DIRECTORY = {t["Device Name"]: t for t in TENANTS}

def calculate_cost(kwh):
    return (kwh * 0.44) + 30.0

def main():
    if not USERNAME or not PASSWORD or not GOOGLE_SCRIPT_URL:
        print("Missing environment variables.")
        return

    vue = PyEmVue()
    vue.login(username=USERNAME, password=PASSWORD)
    devices = vue.get_devices()

    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Calculate previous full month range
    if now.month == 1:
        prev_start = datetime.datetime(now.year - 1, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        prev_end = datetime.datetime(now.year, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    else:
        prev_start = datetime.datetime(now.year, now.month - 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        prev_end = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    
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

    prev_raw_data = []
    for item in devices_map:
        dev_name = item["name"]
        t_info = TENANT_DIRECTORY.get(dev_name, {"Tenant": "Unknown", "Phone": ""})
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
                "Tenant": t_info["Tenant"],
                "Phone": t_info["Phone"],
                "Usage (kWh)": round(total_usage, 2),
                "Estimated Cost ($)": round(est_cost, 2)
            })
        except Exception:
            prev_raw_data.append({
                "Device Name": dev_name,
                "Tenant": t_info["Tenant"],
                "Phone": t_info["Phone"],
                "Usage (kWh)": 0.0,
                "Estimated Cost ($)": 30.0
            })

    now_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows_to_send = []
    for r in prev_raw_data:
        rows_to_send.append([
            now_timestamp,
            prev_month_name,
            r["Device Name"],
            r["Tenant"],
            str(r["Phone"]),
            r["Usage (kWh)"],
            r["Estimated Cost ($)"]
        ])

    response = requests.post(
        GOOGLE_SCRIPT_URL,
        json={"rows": rows_to_send}
    )
    print(f"Response status: {response.status_code}, body: {response.text}")

if __name__ == "__main__":
    main()