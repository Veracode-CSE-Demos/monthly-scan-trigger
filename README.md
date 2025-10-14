
# Veracode GitHub Monthly Scanner

This repository automates **Veracode static scans** for GitHub-hosted code using:

* **Veracode CLI** → packages source code into ZIP artifacts
* **Veracode Java API Wrapper** → uploads artifacts and triggers scans
* **GitHub Actions** → orchestrates and schedules scans

It reads Veracode application profiles, finds associated GitHub repositories (`org/repo`), clones them, packages the code, and triggers scans if the most recent static scan is older than **30 days**.

---

## Setup Instructions

### Required GitHub Secrets

| Secret Name        | Description                              |
| ------------------ | ---------------------------------------- |
| `VERACODE_API_ID`  | Your Veracode API ID                     |
| `VERACODE_API_KEY` | Your Veracode API Key                    |
| `GH_PAT`           | GitHub Personal Access Token (see below) |

To add them:

1. Go to **Settings → Secrets and variables → Actions** in your repository.
2. Click **New repository secret** and add each of the above.

---

### Generate and Authorize a GitHub Personal Access Token (`GH_PAT`)

1. Visit [https://github.com/settings/tokens](https://github.com/settings/tokens).
2. Under **“Fine-grained tokens”**, select **Generate new token → Personal Access Token (classic)**.
3. Give it a descriptive name (e.g. `veracode-scan-pat`) and choose:

   * **Expiration:** as required by your org (90 days recommended).
   * **Scope:** `repo` (needed to clone private repos).
4. Click **Generate token**, then copy the value shown — GitHub will only display it once.
5. If your organization **enforces SAML SSO**, you’ll now see a section titled **“SSO Authorization”** below the token:

   * Click **Configure SSO**.
   * Check the box next to your organization name.
   * Click **Authorize**.
   * It should now display:

     > “Authorized for: *your-org-name*”
6. If your organization **does not enforce SSO**, this section will **not appear** — that’s normal, and no extra action is needed.
7. Add the token as a secret named `GH_PAT` in your repository (Settings → Secrets → Actions).

---

### How It Works

1. The workflow (`.github/workflows/veracode-scan-orchestrator.yml`) runs daily at **6 AM UTC** or manually via “Run workflow.”
2. The Python script (`scan_check_trigger.py`):

   * Fetches all Veracode applications via the REST API.
   * Finds corresponding GitHub repos using the app’s `org/repo` naming.
   * Clones the repo using your **SAML-authorized PAT**.
   * Packages the code with the **Veracode CLI**.
   * Uploads the artifact and triggers a scan through the **Java API Wrapper**.
   * Skips scanning if the last static scan is less than **30 days old**.

---

### Tools Used

* [Veracode CLI](https://docs.veracode.com/r/veracode_package)
* [Veracode Java API Wrapper](https://docs.veracode.com/r/r_uploadfile)
* [GitHub Actions](https://docs.github.com/en/actions)

---

### Notes

* The PAT (`GH_PAT`) must belong to a user or bot account with read access to the target repositories.
* If your organization later enables SAML SSO, you’ll need to return to the token page and click **Configure SSO → Authorize** to continue using it.
* Tokens or SSH keys that are not authorized for an SSO-enforced org will trigger:

  > “The organization has enabled or enforces SAML SSO.”

