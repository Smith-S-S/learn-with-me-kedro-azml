# Azure ML → GitHub Sync

## Step 1 — Go to the project

```bash
cd /mnt/batch/tasks/shared/LS_root/mounts/clusters/ci-house-price/code/Users/learnwith21/learn-with-me-kedro-azml
```

## Step 2 — Fix Git ownership

```bash
git config --global --add safe.directory /mnt/batch/tasks/shared/LS_root/mounts/clusters/ci-house-price/code/Users/learnwith21/learn-with-me-kedro-azml
```

## Step 3 — Check Git

```bash
git status
```

## Step 4 — Login to GitHub

```bash
gh auth login
```

Select:

```text
GitHub.com
```

Then:

```text
HTTPS
```

Then:

```text
Yes
```

Then:

```text
Login with a web browser
```

## Step 5 — GitHub Device Login

The terminal will show:

```text
First copy your one-time code: XXXXX-XXXXX
```

Open this URL on your laptop:

```text
https://github.com/login/device
```

Enter the one-time code from the Azure ML terminal.

Complete the GitHub authorization.

## Step 6 — Verify GitHub login

Back in the Azure ML terminal:

```bash
gh auth status
```

You should see:

```text
Logged in to github.com
```

## Step 7 — Check GitHub repository

```bash
git remote -v
```

If you see:

```text
origin  https://github.com/USERNAME/REPOSITORY.git (fetch)
origin  https://github.com/USERNAME/REPOSITORY.git (push)
```

your project is already connected.

## Step 8 — If there is no remote

Add your GitHub repository:

```bash
git remote add origin https://github.com/USERNAME/REPOSITORY.git
```

Then check:

```bash
git remote -v
```

## Step 9 — Get latest code from GitHub

Before working:

```bash
git pull origin main
```

## Step 10 — Check changes

```bash
git status
```

## Step 11 — Add changes

```bash
git add .
```

## Step 12 — Commit changes

```bash
git commit -m "Update project"
```

## Step 13 — Push changes to GitHub

```bash
git push origin main
```

## Daily Workflow

### Get latest code

```bash
git pull origin main
```

### Work on the project

Make your code changes.

### Check changes

```bash
git status
```

### Save changes

```bash
git add .
git commit -m "Update project"
git push origin main
```

## Quick Version

```bash
git pull origin main

# Make changes

git status
git add .
git commit -m "Update project"
git push origin main
```

## Important

Do not commit:

```text
.env
passwords
API keys
Azure credentials
access tokens
secrets
```

Check `.gitignore` before running:

```bash
git add .
```
