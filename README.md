

## Veracode GitHub Auto Scanner

This repo automates **Veracode static scans** for GitHub-hosted code using:

- **Veracode CLI** (for packaging)
- **Java API wrapper** (for uploading + scanning)
- **GitHub Actions** (for orchestration)

It reads Veracode app profiles, clones GitHub repos matching `org/repo`, packages them, and triggers scans if the latest scan is older than 30 days.

---

## Setup Instructions

### Required GitHub Secrets

| Secret Name       | Description                                 |
|-------------------|---------------------------------------------|
| `VERACODE_API_ID` | Your Veracode API ID                        |
| `VERACODE_API_KEY`| Your Veracode API Key                       |
| `GH_PAT`          | GitHub Personal Access Token (see below)    |

To add them:
1. Go to **Settings → Secrets and variables → Actions** in your repo.
2. Click **“New repository secret”** and add the above secrets.

---

### Generate a GitHub Personal Access Token (`GH_PAT`)

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Create a **Personal Access Token (classic)** with:
   - `repo` scope (to clone private repos)
   - This PAT would need to be setup with access to the desired orgs repos.
3. Add it to your repo as `GH_PAT`.

---

## Tools Used

- [Veracode CLI](https://docs.veracode.com/r/veracode_package)
- [Veracode Java API Wrapper](https://docs.veracode.com/r/r_uploadfile)

---
