import streamlit as st
import requests
import base64
import json
import math
from datetime import datetime, timedelta
from pyemvue import PyEmVue

# Page configuration
st.set_page_config(
    page_title="Emporia Energy & Tenant Dashboard",
    page_icon="⚡",
    layout="wide"
)

# Load secrets
try:
    EMPORIA_USERNAME = st.secrets["EMPORIA_USERNAME"]
    EMPORIA_PASSWORD = st.secrets["EMPORIA_PASSWORD"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]
except Exception as e:
    st.error("Missing required secrets in Streamlit configuration. Please check your TOML settings.")
    st.stop()

GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_REPO}"

# GitHub API Helper Functions
def load_tenants_from_github():
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    url = f"{GITHUB_API_BASE}/contents/tenants.json"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        file_data = response.json()
        decoded_content = base64.b64decode(file_data["content"]).decode("utf-8")
        return json.loads(decoded_content), file_data.get("sha")
    elif response.status_code == 404:
        # Default fallback if tenants.json doesn't exist yet
        return {}, None
    else:
        st.error(f"GitHub Error {response.status_code}: Check token permissions.")
        return {}, None

def save_tenants_to_github(tenants_data, sha):
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    url = f"{GITHUB_API_BASE}/contents/tenants.json"
    
    file_content = json.dumps(tenants_data, indent=4)
    encoded_content = base64.b64encode(file_content.encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": "Update tenants.json configuration via Streamlit dashboard",
        "content": encoded_content
    }
    if sha:
        payload["sha"] = sha
        
    response = requests.put(url, headers=headers, json=payload)
    if response.status_code in [200, 201]:
        st.success("Successfully synced tenant configuration to GitHub!")
        return True
    else:
        st.error(f"Failed to save to GitHub: {response.json().get('message', response.text)}")
        return false

# Emporia Data Fetching with Diagnostic Logging
@st.cache_data(ttl=600)
def fetch_emporia_data(username, password):
    vue = PyEmVue()
    try:
        success = vue.login(username=username, password=password)
        if not success:
            st.error("Emporia login returned False. AWS Cognito may be blocking Streamlit's IP network.")
            return None, None
    except Exception as e:
        st.error(f"Detailed Emporia Login Error: {str(e)}")
        return None, None

    try:
        devices = vue.get_devices()
        usage_data = {}
        # Fetch usage for devices/circuits here based on standard pyemvue logic
        return devices, vue
    except Exception as e:
        st.error(f"Error fetching Emporia device data: {str(e)}")
        return None, None

# Main Dashboard UI
st.title("⚡ Emporia Energy Usage Dashboard")

# Load persistent tenant state from GitHub
tenants, file_sha = load_tenants_from_github()

# Sidebar for Tenant & Circuit Configuration
st.sidebar.header("Tenant & Circuit Mapping")
tenant_name = st.sidebar.text_input("Tenant Name")
circuit_id = st.sidebar.text_input("Circuit / Device ID")

if st.sidebar.button("Save Tenant Mapping"):
    if tenant_name and circuit_id:
        tenants[tenant_name] = {"circuit_id": circuit_id}
        success = save_tenants_to_github(tenants, file_sha)
        if success:
            st.rerun()
    else:
        st.sidebar.error("Please enter both a tenant name and circuit ID.")

st.sidebar.markdown("---")
st.sidebar.subheader("Configured Tenants")
if tenants:
    for t_name, t_info in list(tenants.items()):
        col1, col2 = st.sidebar.columns([3, 1])
        col1.text(f"{t_name} (ID: {t_info['circuit_id']})")
        if col2.button("Delete", key=f"del_{t_name}"):
            del tenants[t_name]
            updated_sha = load_tenants_from_github()[1]
            save_tenants_to_github(tenants, updated_sha)
            st.rerun()
else:
    st.sidebar.info("No tenants configured yet.")

# Main Content Area - Energy Data
if st.button("🔄 Refresh Energy Data"):
    st.cache_data.clear()
    st.rerun()

devices, vue_client = fetch_emporia_data(EMPORIA_USERNAME, EMPORIA_PASSWORD)

if devices:
    st.success("Successfully connected to Emporia Energy API!")
    # Render usage metrics and cost calculation formula: math.ceil((kwh * 0.44) + 30.0)
    st.write("### Real-Time Usage Breakdown")
    # Add your usage display loop here
else:
    st.warning("Could not load real-time energy data automatically. Please check your credentials or network status.")
