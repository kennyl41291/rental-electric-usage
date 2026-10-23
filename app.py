def save_tenants(df):
    """Pushes tenant updates from the dashboard straight to GitHub, creating the file if missing."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        st.error("GitHub credentials missing in secrets!")
        return

    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{TENANT_FILE}"
    
    try:
        # Check if the file already exists to get its SHA
        get_res = requests.get(url, headers=headers, timeout=10)
        sha = get_res.json().get("sha") if get_res.status_code == 200 else None

        json_str = df.to_json(orient="records", indent=4)
        encoded_content = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

        payload = {
            "message": "Update tenants via Streamlit Dashboard [skip ci]",
            "content": encoded_content,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha  # Only include SHA if the file already exists

        put_res = requests.put(url, headers=headers, json=payload, timeout=10)
        if put_res.status_code in [200, 201]:
            st.sidebar.success("Saved & pushed to GitHub!")
            st.cache_data.clear()
        else:
            st.sidebar.error(f"Failed to push to GitHub: {put_res.text}")
    except Exception as e:
        st.sidebar.error(f"Error saving to GitHub: {e}")
