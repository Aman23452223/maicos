# Vercel deploy via GitHub Actions (OIDC, no tokens)

This is the **tokenless** path. No `VERCEL_TOKEN` lives in GitHub
secrets, no PAT in chat. The deploy happens through GitHub's OIDC
trust with Vercel.

You do this **once**, then every push to `main` deploys and every PR
gets a preview URL — automatically.

---

## 1. Create the Vercel project (one-time)

If the project doesn't exist yet:

```bash
# From the repo root, on your machine, with the Vercel CLI installed
# (npm i -g vercel)
vercel link --yes
cd frontend
vercel
```

Or in the dashboard: https://vercel.com/new → **Import Git Repository**
→ pick `maicos` → set **Root Directory = `frontend`** → **Deploy**.

**Do not** add `NEXT_PUBLIC_API_URL` yet (we'll do that in §3).

---

## 2. Enable Vercel OIDC for GitHub Actions

Vercel supports OIDC since 2024. To use it:

### Option A — from the Vercel dashboard (recommended)

1. Open the project → **Settings** → **Git** → scroll to **OIDC Token**
   (or the "Deploy hooks / Git integrations" section).
2. **Enable** the OIDC trust for the GitHub repo.
3. Copy the **OIDC Token** value. It is *short-lived* and is **not** a
   classic API token — Vercel hands it to GitHub Actions only after
   verifying the workflow's identity.

### Option B — via the CLI

```bash
# In the project directory
vercel env pull   # confirm you can talk to the project
# OIDC setup is currently dashboard-only; check Vercel docs if it has
# moved: https://vercel.com/docs/security/oidc
```

If Vercel does not yet expose OIDC for your plan/account, use the
fallback in §5 (classic token, but scoped + rotated regularly).

---

## 3. Add the OIDC token to GitHub secrets

GitHub repo → **Settings** → **Secrets and variables** → **Actions** →
**New repository secret**:

- **Name:** `VERCEL_OIDC_TOKEN`
- **Value:** the OIDC token value from §2

That's the only secret this workflow needs.

Add a second one for the live API base:

- **Name:** `NEXT_PUBLIC_API_URL`
- **Value:** `https://your-backend.example.com` (or whatever URL your
  backend is reachable at)

You can also add the same key in **Vercel → Settings → Environment
Variables** so production reads it at runtime.

---

## 4. Configure GitHub branch protection

Repo → **Settings** → **Branches** → **Branch protection rules** →
**Add rule** for `main`:

- ✅ Require a pull request before merging
- ✅ Require approvals: **1**
- ✅ Require status checks to pass before merging:
  - `test` (from `backend.yml`)
  - `build` (from `frontend.yml`)
- ✅ Require linear history
- ✅ Do not allow force pushes

---

## 5. Fallback — classic Vercel token (only if OIDC is unavailable)

If OIDC isn't an option in your plan or region, use a **scoped**
classic token. Short-lived, project-scoped, rotated regularly.

1. https://vercel.com/account/tokens → **Create Token**
2. Scope: **the MAICOS project only**, **1-day expiry** if you only
   deploy once, otherwise **30-day expiry max**.
3. Add it as GitHub secret `VERCEL_TOKEN`.
4. Replace the OIDC step in `.github/workflows/vercel.yml` with:

   ```yaml
   - name: Install Vercel CLI
     run: npm install -g vercel@latest
   - name: Pull Vercel environment
     run: vercel pull --yes --environment=production
     env:
       VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
   - name: Build
     run: vercel build --prod
     env:
       VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
   - name: Deploy
     run: vercel deploy --prebuilt --prod --yes
     env:
       VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
   ```

5. **Set a calendar reminder** to rotate the token. Never reuse a
   leaked token.

---

## 6. What happens after you push

- **PR opened / updated** → GitHub runs `backend`, `frontend`, and
  `vercel` (preview). Vercel comments on the PR with a preview URL.
- **Push to `main`** → `vercel` deploys to production. Backend CI runs
  on every push too, so you cannot merge a broken backend.
- **Failed backend CI** → the **Required status checks** rule blocks
  the merge.

---

## 7. Revoke & rotate

- **VERCEL_OIDC_TOKEN** (or **VERCEL_TOKEN**) — rotate at least every
  90 days, immediately on any leak.
- **GitHub PATs** — never paste them anywhere. If you need a PAT, use
  `gh auth login` so it's stored in the OS keychain.

---

## Quick checklist

- [ ] Vercel project created, root = `frontend`
- [ ] Vercel OIDC enabled for the repo
- [ ] `VERCEL_OIDC_TOKEN` added to GitHub secrets
- [ ] `NEXT_PUBLIC_API_URL` set in GitHub secrets *and* in Vercel env
- [ ] Branch protection enabled on `main`
- [ ] First test push to a feature branch → PR preview URL appears
- [ ] Merge to `main` → production URL appears in workflow summary
