import datetime
import os
import json
import math
import zoneinfo
import requests
from pyemvue import PyEmVue
from pyemvue.enums import Scale, Unit

USERNAME = os.environ.get("EMPORIA_USERNAME")
PASSWORD = os.environ.get("EMPORIA_PASSWORD")
GOOGLE_SCRIPT_URL = os.environ.get("GOOGLE_SCRIPT_URL")

TENANT_FILE = "tenants.json"

DEFAULT_TENANTS = [
    {"Device Name": "1631 74th St Basement Rear", "Tenant": "Shaheer", "Phone": "2022904910"},
    {"Device Name": "1563 70th St Basement Front", "Tenant": "Francisco", "Phone": "9295498478"},
    {"Device Name": "1563 70th St 1F", "Tenant": "Marcos", "Phone": "9179821594"},
    {"Device Name": "6628 Wallaston 1F", "Tenant": "Edwin", "Phone": "9297052008"},
    {"Device Name": "1563 70th st 1Rear", "Tenant": "Angel", "Phone": "2016405388"},
    {"Device Name": "1563 70th st Basement Rear", "Tenant": "N/A", "Phone": ""}
]

def load_tenant_directory():
    if os.path.exists(TENANT_FILE):
        try:
            with open(TENANT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {t["Device Name"]: t for t in data}
        except Exception as e:
            print(f"Error loading {TENANT_FILE}: {e}")
    return {t["Device Name"]: t for t in DEFAULT_TENANTS}

def calculate_cost(kwh):
    raw_cost = (kwh * 0.44) + 30.0
    return math.ceil(raw_cost)  # Matches your whole-dollar rounding rule

def main():
    if not USERNAME or not PASSWORD or not GOOGLE_SCRIPT_URL:
        print("Missing environment variables.")
        return

    TENANT_DIRECTORY = load_tenant_directory()

    vue = PyEmVue()
    vue.login(username=USERNAME, password=PASSWORD)
    devices = vue.get_devices()

    est_tz = zoneinfo.ZoneInfo("America/New_York")
    now = datetime.datetime.now(est_tz)
    
    if now.month == 1:
        prev_start = datetime.datetime(now.year - 1, 12, 1, 0, 0, 0, tzinfo=est_tz)
        prev_end = datetime.datetime(now.year, 1, 1, 0, 0, 0, tzinfo=est_tz)
    else:
        prev_start = datetime.datetime(now.year, now.month - 1, 1, 0, 0, 0, tzinfo=est_tz)
        prev_end = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=est_tz)
    
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
        
        # Only process devices that exist in your tenant directory to ignore extra meters
        if dev_name not in TENANT_DIRECTORY:
            continue
            
        t_info = TENANT_DIRECTORY[dev_name]
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
                "Tenant": t_info.get("Tenant", "Unknown"),
                "Phone": t_info.get("Phone", ""),
                "Usage (kWh)": round(total_usage, 2),
                "Estimated Cost ($)": est_cost
            })
        except Exception:
            prev_raw_data.append({
                "Device Name": dev_name,
                "Tenant": t_info.get("Tenant", "Unknown"),
                "Phone": t_info.get("Phone", ""),
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

    headers = {'Content-Type': 'application/json'}
    response = requests.post(
        GOOGLE_SCRIPT_URL,
        json={"rows": rows_to_send},
        headers=headers
    )
    print(f"Response status: {response.status_code}, body: {response.text}")

if __name__ == "__main__":
    main()
