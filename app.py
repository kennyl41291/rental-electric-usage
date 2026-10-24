import datetime
import os
import json
import math
import urllib.parse
import zoneinfo
import base64
import io
import requests
import streamlit as st
import pandas as pd
from pyemvue import PyEmVue
from pyemvue.enums import Scale, Unit

# Page Config
st.set_page_config(page_title="Emporia Energy Dashboard", page_icon="⚡", layout="wide")

# Environment Variables (Configured safely for Render & Local)
USERNAME = "kennyl41291@gmail.com"
PASSWORD = "19585723a"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # e.g., "your-username/your-repo-name"

EMPORIA_USERNAME = os.getenv("EMPORIA_USERNAME", USERNAME)
EMPORIA_PASSWORD = os.getenv("EMPORIA_PASSWORD", PASSWORD)

TENANT_FILE = "tenants.json"

DEFAULT_TENANTS = [
    {"Device Name": "1631 74th St Basement Rear", "Tenant": "Shaheer", "Phone": "2022904910"},
    {"Device Name": "1563 70th St Basement Front", "Tenant": "Francisco", "Phone": "9295498478"},
    {"Device Name": "1563 70th St 1F", "Tenant": "Marcos", "Phone": "9179821594"},
    {"Device Name": "6628 Wallaston 1F", "Tenant": "Edwin", "Phone": "9297052008"},
    {"Device Name": "1563 70th st 1Rear", "Tenant": "Angel", "Phone": "2016405388"},
    {"Device Name": "1563 70th st Basement Rear", "Tenant": "N/A", "Phone": ""}
]

@st.cache_data(ttl=60)
def load_tenants():
    """Fetches tenants.json directly from GitHub so the dashboard is always live."""
    if GITHUB_TOKEN and GITHUB_REPO:
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{TENANT_FILE}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                file_content = res.json().get("content")
                decoded = base64.b64decode(file_content).decode("utf-8")
                df = pd.read_json(io.StringIO(decoded))
                if "gid" not in df.columns:
                    df["gid"] = None
                return df
        except Exception as e:
            st.warning(f"Could not load from GitHub: {e}")
    df = pd.DataFrame(DEFAULT_TENANTS)
    df["gid"] = None
    return df

def save_tenants(df):
    """Pushes tenant updates straight to GitHub, robustly handling file creation or updates."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        st.error("GitHub credentials missing in secrets!")
        return

    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{TENANT_FILE}"
    
    try:
        json_str = df.to_json(orient="records", indent=4)
        encoded_content = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

        sha = None
        get_res = requests.get(url, headers=headers, timeout=5)
        if get_res.status_code == 200:
            sha = get_res.json().get("sha")

        payload = {
            "message": "Update tenants via Streamlit Dashboard [skip ci]",
            "content": encoded_content,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha

        put_res = requests.put(url, headers=headers, json=payload, timeout=10)
        if put_res.status_code in [200, 201]:
            st.success("Tenant changes saved & pushed to GitHub successfully!")
            st.cache_data.clear()
        else:
            st.error(f"GitHub Error {put_res.status_code} for repo '{GITHUB_REPO}': Check token permissions.")
    except Exception as e:
        st.error(f"Error saving to GitHub: {e}")

def calculate_cost(kwh):
    raw_cost = (kwh * 0.44) + 30.0
    return math.ceil(raw_cost)

@st.cache_data(ttl=600)
def fetch_emporia_data(username, password):
    vue = PyEmVue()
    try:
        success = vue.login(username=username, password=password)
        if not success:
            st.error("⚠️ Emporia login returned False. AWS Cognito is actively blocking Streamlit's cloud IP address.")
            return None, None, None, None
    except Exception as e:
        st.error(f"⚠️ Emporia Authentication Exception: {e}")
        return None, None, None, None

    try:
        devices = vue.get_devices()
    except Exception as e:
        st.error(f"⚠️ Error retrieving devices from Emporia API: {e}")
        return None, None, None, None

    est_tz = zoneinfo.ZoneInfo("America/New_York")
    now = datetime.datetime.now(est_tz)
    
    if now.month == 1:
        prev_start = datetime.datetime(now.year - 1, 12, 1, 0, 0, 0, tzinfo=est_tz)
        prev_end = datetime.datetime(now.year, 1, 1, 0, 0, 0, tzinfo=est_tz)
    else:
        prev_start = datetime.datetime(now.year, now.month - 1, 1, 0, 0, 0, tzinfo=est_tz)
        prev_end = datetime.datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=est_tz)

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
        gid = item["gid"]
        dev_name = item["name"]
        
        try:
            usage_prev, _ = vue.get_chart_usage(item["channel"], start=prev_start, end=prev_end, scale=Scale.DAY.value, unit=Unit.KWH.value)
            tot_prev = sum(v for v in usage_prev if v is not None) if usage_prev else 0.0
        except Exception:
            tot_prev = 0.0
        prev_data.append({"gid": gid, "Device Name": dev_name, "Usage (kWh)": round(tot_prev, 2), "Estimated Cost ($)": calculate_cost(tot_prev)})

        try:
            usage_curr, _ = vue.get_chart_usage(item["channel"], start=curr_start, end=curr_end, scale=Scale.DAY.value, unit=Unit.KWH.value)
            tot_curr = sum(v for v in usage_curr if v is not None) if usage_curr else 0.0
        except Exception:
            tot_curr = 0.0
        curr_data.append({"gid": gid, "Device Name": dev_name, "Usage (kWh)": round(tot_curr, 2), "Estimated Cost ($)": calculate_cost(tot_curr)})

    prev_month_label = prev_start.strftime('%B %Y')
    curr_month_label = f"{curr_start.strftime('%B %Y')} (MTD)"

    return pd.DataFrame(prev_data), pd.DataFrame(curr_data), prev_month_label, curr_month_label

# Main UI
st.title("⚡ Emporia Energy Usage Dashboard")

if "tenant_df" not in st.session_state:
    st.session_state.tenant_df = load_tenants()

# --- MOBILE-FRIENDLY TENANT EDITOR (NO SCROLLING & LOCKED DEVICES) ---
with st.expander("🏢 Manage & Edit Tenant Directory (GitHub Sync)", expanded=False):
    st.markdown("Update tenant names and phone numbers below. Device names are locked, and no horizontal scrolling is required.")
    
    updated_rows = []
    df_current = st.session_state.tenant_df
    
    for index, row in df_current.iterrows():
        cols = st.columns([2, 2, 1.5])
        with cols[0]:
            st.text_input("Device Name", value=str(row["Device Name"]), disabled=True, key=f"dev_{index}")
        with cols[1]:
            t_name = st.text_input("Tenant Name", value=str(row["Tenant"]), key=f"tenant_{index}")
        with cols[2]:
            t_phone = st.text_input("Phone", value=str(row["Phone"]), key=f"phone_{index}")
            
        updated_rows.append({
            "gid": row.get("gid"),
            "Device Name": row["Device Name"],
            "Tenant": t_name,
            "Phone": t_phone
        })
        st.divider()
        
    if st.button("💾 Save Directory Changes", type="primary"):
        new_df = pd.DataFrame(updated_rows)
        st.session_state.tenant_df = new_df
        save_tenants(new_df)
        st.rerun()

st.markdown("---")

if not USERNAME or not PASSWORD:
    st.error("Please configure credentials.")
else:
    if "df_curr" not in st.session_state:
        try:
            res = fetch_emporia_data(USERNAME, PASSWORD)
            if res[0] is not None:
                df_prev, df_curr, prev_label, curr_label = res
                st.session_state.df_prev = df_prev
                st.session_state.df_curr = df_curr
                st.session_state.prev_label = prev_label
                st.session_state.curr_label = curr_label
        except Exception as e:
            st.error(f"Failed to fetch Emporia data automatically: {e}")

    if st.button("🔄 Refresh Energy Data", type="primary"):
        with st.spinner("Connecting to Emporia..."):
            try:
                res = fetch_emporia_data(USERNAME, PASSWORD)
                if res[0] is not None:
                    df_prev, df_curr, prev_label, curr_label = res
                    st.session_state.df_prev = df_prev
                    st.session_state.df_curr = df_curr
                    st.session_state.prev_label = prev_label
                    st.session_state.curr_label = curr_label
                    st.success("Data refreshed successfully!")
                else:
                    st.warning("Could not refresh live data feed due to AWS Cognito cloud IP restrictions.")
            except Exception as e:
                st.error(f"Failed to fetch Emporia data: {e}")

    if "df_curr" in st.session_state and st.session_state.df_curr is not None:
        # --- AUTO-SYNC & AUTO-RENAME BY GID ---
        tenant_df = st.session_state.tenant_df
        emporia_curr = st.session_state.df_curr
        
        if "gid" not in tenant_df.columns:
            tenant_df["gid"] = None
            
        updated_directory = False
        
        for _, emp_row in emporia_curr.iterrows():
            e_gid = emp_row["gid"]
            e_name = emp_row["Device Name"]
            
            # Match by GID first
            match = tenant_df[tenant_df["gid"] == e_gid]
            if not match.empty:
                idx = match.index[0]
                if tenant_df.at[idx, "Device Name"] != e_name:
                    tenant_df.at[idx, "Device Name"] = e_name
                    updated_directory = True
            else:
                # Fallback check by name for initial migration
                name_match = tenant_df[(tenant_df["Device Name"] == e_name) & (tenant_df["gid"].isna() | (tenant_df["gid"] == ""))]
                if not name_match.empty:
                    idx = name_match.index[0]
                    tenant_df.at[idx, "gid"] = e_gid
                    updated_directory = True
                else:
                    # Brand new device discovered from Emporia!
