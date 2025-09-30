import os
import subprocess
import shutil
from datetime import datetime, timezone
import requests

from veracode_api_signing.plugin_requests import RequestsAuthPluginVeracodeHMAC

# Base settings
VERACODE_API_BASE = "https://api.veracode.com/appsec/v1"
ARTIFACTS_DIR = "scan-artifacts"
CLONE_DIR = "temp-repo"
SCAN_THRESHOLD_DAYS = 30
JAVA_WRAPPER_JAR = "vosp-api-wrapper-java.jar"

# Secrets from environment
API_ID = os.environ.get("VERACODE_API_ID")
API_KEY = os.environ.get("VERACODE_API_KEY")
GH_PAT = os.environ.get("GH_PAT")

if not all([API_ID, API_KEY, GH_PAT]):
    raise EnvironmentError("[ERROR] Missing required environment variables.")

# Create a signed Veracode session
def veracode_session():
    session = requests.Session()
    auth = RequestsAuthPluginVeracodeHMAC()
    auth.api_key_id = API_ID
    auth.api_key_secret = API_KEY
    session.auth = auth
    return session

# Get all application profiles
def get_all_applications():
    print("[INFO] Fetching Veracode application profiles...")
    url = f"{VERACODE_API_BASE}/applications"
    session = veracode_session()
    resp = session.get(url)
    resp.raise_for_status()
    data = resp.json()
    apps = data.get("_embedded", {}).get("applications", [])

    app_map = {}
    for app in apps:
        guid = app["guid"]
        name = app.get("profile", {}).get("name", guid)
        app_map[guid] = name
    return app_map

# Get the latest STATIC scan for one app
def get_latest_static_scan(app_guid):
    url = f"{VERACODE_API_BASE}/applications/{app_guid}"
    session = veracode_session()
    resp = session.get(url)

    if resp.status_code != 200:
        return None

    scans = resp.json().get("scans", [])
    latest_scan = None
    latest_date = ""

    for scan in scans:
        scan_type = scan.get("scan_type")
        if scan_type not in (None, "STATIC"):
            continue

        modified_date = scan.get("modified_date") or ""
        if modified_date > latest_date:
            latest_date = modified_date
            latest_scan = scan

    return latest_scan

# Check if scan is older than threshold
def is_scan_outdated(scan_date, threshold_days=30):
    if not scan_date:
        return True
    dt = datetime.fromisoformat(scan_date.replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - dt).days
    return age_days > threshold_days

# Clone a GitHub repo
def clone_repo(app_name):
    if "/" not in app_name:
        raise ValueError(f"Invalid app name '{app_name}'. Must be org/repo.")

    org, repo = app_name.split("/", 1)
    url = f"https://{GH_PAT}:x-oauth-basic@github.com/{org}/{repo}.git"

    if os.path.exists(CLONE_DIR):
        shutil.rmtree(CLONE_DIR)

    print(f"[INFO] Cloning repo {org}/{repo}...")
    subprocess.run(["git", "clone", url, CLONE_DIR], check=True)

# Package repo into artifacts
def autopackage(app_name):
    output_dir = os.path.join(ARTIFACTS_DIR, app_name.replace("/", "_"))
    os.makedirs(output_dir, exist_ok=True)
    print(f"[INFO] Packaging source for {app_name}...")

    result = subprocess.run(
        [
            "veracode", "package",
            "--source", CLONE_DIR,
            "--trust",
            "--output", output_dir,
            "--verbose"
        ],
        check=True,
        capture_output=True,
        text=True
    )

    artifacts = []
    for f in os.listdir(output_dir):
        if f.endswith(".zip"):
            artifacts.append(os.path.join(output_dir, f))
    return artifacts

# Upload and trigger a policy scan
def upload_and_scan(app_name, artifact_paths):
    if not artifact_paths:
        raise RuntimeError("No artifacts to upload.")

    artifact_dir = os.path.dirname(artifact_paths[0])
    version = f"policy-scan-{datetime.now().strftime('%Y%m%d%H%M')}"
    print(f"[INFO] Starting policy scan for {app_name}...")

    subprocess.run([
        "java", "-jar", JAVA_WRAPPER_JAR,
        "-action", "uploadandscan",
        "-vid", API_ID,
        "-vkey", API_KEY,
        "-appname", app_name,
        "-createprofile", "false",
        "-version", version,
        "-filepath", artifact_dir
    ], check=True)

# Main flow
def main():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    apps = get_all_applications()

    for guid, app_name in apps.items():
        print(f"\n[INFO] Checking {app_name}...")

        scan = get_latest_static_scan(guid)
        last_date = scan.get("modified_date") if scan else None

        if is_scan_outdated(last_date, SCAN_THRESHOLD_DAYS):
            print(f"[INFO] Outdated scan (last: {last_date})")

            if "/" not in app_name:
                print(f"[WARN] Skipping app with no repo mapping: {app_name}")
                continue

            try:
                clone_repo(app_name)
                artifacts = autopackage(app_name)
                print(f"[INFO] Found {len(artifacts)} artifact(s).")
                upload_and_scan(app_name, artifacts)
            except Exception as e:
                print(f"[ERROR] Failed to scan {app_name}: {e}")
            finally:
                if os.path.exists(CLONE_DIR):
                    shutil.rmtree(CLONE_DIR)
        else:
            print(f"[INFO] Scan is up to date (last: {last_date})")

if __name__ == "__main__":
    main()
