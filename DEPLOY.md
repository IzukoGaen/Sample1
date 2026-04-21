# Deployment for the team (Streamlit Community Cloud + GitHub)

This app is a **Streamlit** UI at the repo root (`streamlit_app.py`). The recommended shared setup is **GitHub** as source of truth and **Streamlit Community Cloud** to host the live URL.

Choose how strict access must be:

| Goal | Approach |
|------|----------|
| **Private GitHub repo + app not open to the internet** | Streamlit Community Cloud from a **private** repo, app set to **private** + invited viewers (see [Private repo and private app](#private-repo-and-private-app-non-public)) |
| **Full corporate control (VPC, SSO, no Streamlit Cloud)** | **Self-host** Streamlit (or FastAPI + your own UI) on an internal VM / Kubernetes / Azure—out of scope for this short doc; use the same `requirements.txt` in your container image |

## Roles

| Role | Tasks |
|------|--------|
| **Admin** | GitHub repo (settings, branch protection), Streamlit Cloud workspace, connect repo → Cloud, sharing & viewers, rotate access if someone leaves |
| **Developer** | Push to `main` (or open PRs), keep `requirements.txt` accurate, watch [GitHub Actions](.github/workflows/tests.yml) |
| **User** | Open the Cloud URL (sign in if the app is private), upload Original + Test `.xlsx`, download QC result |

## Private repo and private app (non-public)

This matches **private code on GitHub** and **only invited people can open the QC app**.

1. **GitHub:** set the repository to **Private**. Add collaborators with **Read** or **Write** as your policy requires (Streamlit needs permission to pull the repo for builds—connect Streamlit with a GitHub account that has access).

2. **Streamlit Community Cloud:** deploy the app from that **private** repository (same steps as below: New app → branch → `streamlit_app.py`). Per [Share your app](https://docs.streamlit.io/streamlit-community-cloud/share-your-app), an app deployed from a **private** repo is **private by default** (not visible to random internet users).

3. **Sharing:** in [App settings](https://docs.streamlit.io/streamlit-community-cloud/manage-your-app/app-settings) → **Sharing**, set **Who can view this app** to **Only specific people can view this app** if you want to enforce invite-only access (you can also use the **Share** button on the app). Invite teammates **by email**; they sign in with Google or a **single-use link** Streamlit emails, as described in the same docs.

4. **Developers vs viewers:** people with **push/admin on the GitHub repo** can act as developers in Cloud; everyone else needs an explicit **viewer** invite for a private app.

**Important limits (check current Streamlit docs/pricing):** Community Cloud documents a limit of **one private app at a time** per workspace when deploying from private repositories—you may need to make other private apps public or delete them before adding another. Product limits change; confirm on [Streamlit Community Cloud](https://streamlit.io/cloud) before committing to a rollout plan.

**Data note:** a private app controls **who can open the UI**. Uploaded workbooks still flow through Streamlit’s service per their trust and security model—if your compliance team requires **data never leaves your network**, use **self-hosting** instead of Community Cloud.

## One-time setup (admin)

1. **GitHub**
   - Create or use an organization/repo (public or private).
   - Add collaborators under **Settings → Collaborators** (or team access via org).
   - Optional: enable branch protection on `main` and require the **tests** workflow to pass.

2. **Streamlit Community Cloud** ([streamlit.io/cloud](https://streamlit.io/cloud))
   - Sign in with GitHub and authorize Streamlit to access the repository (including **private** repos if you grant that scope).
   - **Create app** → select repository, branch (`main`), **Main file path:** `streamlit_app.py`.
   - In **Advanced settings**, pick **Python 3.12** (or match `requires-python` in [`pyproject.toml`](pyproject.toml)). *Python version may be fixed until you redeploy—see Streamlit docs.*
   - After the first successful build, configure **Sharing** (public vs private + email invites) as in the section above—not everyone needs the raw URL to be world-accessible.

3. **Updates**
   - Pushes to the connected branch trigger redeploys (per Streamlit defaults). Use **Manage app → Reboot** or build logs if something looks stuck.

## Team access on Streamlit Cloud (summary)

- **Public app:** anyone with the URL can use it—fine only for non-sensitive samples.
- **Private app:** use a **private** GitHub repo and/or **Sharing → only specific people**, then **invite viewers by email** ([Share your app](https://docs.streamlit.io/streamlit-community-cloud/share-your-app)).

## Files this deploy relies on

| File | Purpose |
|------|---------|
| [`requirements.txt`](requirements.txt) | `pip` install: Python deps + `-e .` for the `sanitycheck` package |
| [`packages.txt`](packages.txt) | Optional **apt** packages for Cloud (see [Streamlit docs](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/app-dependencies)) |
| [`streamlit_app.py`](streamlit_app.py) | Entrypoint Streamlit runs |

## Optional: secrets

This QC flow does not require API keys. If you later add features that need secrets, use **Streamlit Cloud → App settings → Secrets** and read them in the app with `st.secrets`.

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| **ModuleNotFoundError: sanitycheck** | Cloud’s `uv` step sometimes omits the editable install; `streamlit_app.py` prepends `src/` to `sys.path` as a fallback. Keep `-e .` plus `setuptools`/`wheel` in `requirements.txt`. If it still fails, confirm `src/sanitycheck/` exists on the deployed branch. |
| **Build fails on pip** | Pin incompatible versions; match Python in Cloud to local dev |
| **`git push` / `main` errors** | See [README → Git: first push](README.md#git-first-push--src-refspec-main-does-not-match-any) |
| **App sleeping / slow cold start** | Normal on free tier; upgrade plan or accept delay |
| **User cannot open private app** | Add their email under **Share** / **App settings → Sharing**; they must sign in with the invited identity |

## Local parity (developers)

```bash
python -m pip install -r requirements.txt
py -m streamlit run streamlit_app.py
```

Same dependency path Cloud uses, without Cloud-specific limits.
