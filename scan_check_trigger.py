import os
import subprocess
import shutil
from datetime import datetime, timezone
import requests

from veracode_api_signing.plugin_requests import RequestsAuthPluginVeracodeHMAC

# Constants
VERACODE_API_BASE = "https://api.veracode.com/appsec/v1"
ARTIFACTS_DIR = "scan-artifacts"
CLONE_DIR = "temp-repo"
SCAN_THRESHOLD_DAYS = 30
JAVA_WRAPPER_JAR = "vosp-api-wrapper-java.jar"

# Secrets
API_ID = os.environ.get("VERACODE_API_ID")
API_KEY = os.environ.get("VERACODE_API_KEY")
GH_PAT = os.environ.get("GH_PAT")

if not all([API_ID, API_KEY, GH_PAT]):
    raise EnvironmentError("[ERROR] Required environment variables are not set.")

# Authenticated Veracode session
def veracode_session():
    session = requests.Session()
    auth = RequestsAuthPluginVeracodeHMAC()
    auth.api_key_id = API_ID
    auth.api_key_secret = API_KEY
    session.auth = auth
    return session

def get_all_applications():
    print("[INFO] Fetching Veracode application profiles...")
    url = f"{VERACODE_API_BASE}/applications"
    session = veracode_session()
    resp = session.get(url)
    resp.raise_for_status()
    apps = resp.json().get('_embedded', {}).get('applications', [])
    return {app["guid"]: app.get("profile", {}).get("name", app["guid"]) for app in apps}

def get_latest_static_scan(app_guid):
    url = f"{VERACODE_API_BASE}/applications/{app_guid}"
    session = veracode_session()
    resp = session.get(url)
    if resp.status_code != 200:
        return None
    scans = resp.json().get("scans", [])
    return max((s for s in scans if s.get("scan_type") in [None, "STATIC"]),
               key=lambda s: s.get("modified_date") or "", default=None)

def is_scan_outdated(scan_date, threshold_days=30):
    if not scan_date:
        return True
    dt = datetime.fromisoformat(scan_date.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days > threshold_days

def clone_repo(app_name):
    if "/" not in app_name:
        raise ValueError(f"App name '{app_name}' is not in 'org/repo' format.")

    org, repo = app_name.split("/", 1)
    url = f"https://{GH_PAT}:x-oauth-basic@github.com/{org}/{repo}.git"

    if os.path.exists(CLONE_DIR):
        shutil.rmtree(CLONE_DIR)

    print(f"[INFO] Cloning repo: {url}")
    subprocess.run(["git", "clone", url, CLONE_DIR], check=True)

def autopackage(app_name):
    output_dir = os.path.join(ARTIFACTS_DIR, app_name.replace("/", "_"))
    os.makedirs(output_dir, exist_ok=True)
    print(f"[INFO] Packaging source for: {app_name}...")

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
    return [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".zip")]

def upload_and_scan(app_name, artifact_paths):
    artifact_dir = os.path.dirname(artifact_paths[0])
    version = f"policy-scan-{datetime.now().strftime('%Y%m%d%H%M')}"
    print(f"[INFO] Starting Veracode policy scan for '{app_name}'...")

    try:
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
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Policy scan failed for {app_name}: {e}")
        raise

def main():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    apps = get_all_applications()
    for guid, app_name in apps.items():
        print(f"\n[INFO] Checking: {app_name}")
        scan = get_latest_static_scan(guid)
        last_date = scan.get("modified_date") if scan else None

        if is_scan_outdated(last_date, SCAN_THRESHOLD_DAYS):
            print(f"[INFO] Outdated scan detected (last: {last_date})")

            if "/" not in app_name:
                print(f"[WARN] Skipping non-GitHub app name: {app_name}")
                continue

            try:
                clone_repo(app_name)
                artifacts = autopackage(app_name)
                print(f"[INFO] {len(artifacts)} artifact(s) found.")
                upload_and_scan(app_name, artifacts)
            except Exception as e:
                print(f"[ERROR] Failed to scan {app_name}: {e}")
            finally:
                if os.path.exists(CLONE_DIR):
                    shutil.rmtree(CLONE_DIR)
        else:
            print(f"[INFO] Scan is up to date. Last scan: {last_date}")

if __name__ == "__main__":
    main()
