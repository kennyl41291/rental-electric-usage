import base64
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or st.secrets.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO") or st.secrets.get("GITHUB_REPO")
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
                return pd.read_json(decoded)
        except Exception as e:
            st.warning(f"Could not load from GitHub: {e}")
    return pd.DataFrame(DEFAULT_TENANTS)

def save_tenants(df):
    """Pushes tenant updates from the dashboard straight to GitHub."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        st.error("GitHub credentials missing in secrets!")
        return

    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{TENANT_FILE}"
    
    try:
        # 1. Get the current file's SHA (required by GitHub API to update files)
        get_res = requests.get(url, headers=headers, timeout=10)
        sha = get_res.json().get("sha") if get_res.status_code == 200 else None

        # 2. Convert dataframe to JSON string and base64 encode it
        json_str = df.to_json(orient="records", indent=4)
        encoded_content = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

        # 3. Commit/Push update to GitHub via API
        payload = {
            "message": "Update tenants via Streamlit Dashboard [skip ci]",
            "content": encoded_content,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha

        put_res = requests.put(url, headers=headers, json=payload, timeout=10)
        if put_res.status_code in [200, 201]:
            st.sidebar.success("Saved & pushed to GitHub!")
            st.cache_data.clear()
        else:
            st.sidebar.error(f"Failed to push to GitHub: {put_res.text}")
    except Exception as e:
        st.sidebar.error(f"Error saving to GitHub: {e}")
