# Azure ML → GitHub Sync

## Step 1 — Go to the project

```bash
cd /mnt/batch/tasks/shared/LS_root/mounts/clusters/ci-house-price/code/Users/learnwith21/learn-with-me-kedro-azml
```

## Step 2 — Fix Git ownership

If you get:

```text
fatal: detected dubious ownership
```

run:

```bash
git config --global --add safe.directory /mnt/batch/tasks/shared/LS_root/mounts/clusters/ci-house-price/code/Users/learnwith21/learn-with-me-kedro-azml
```

## Step 3 — Check Git

```bash
git status
```

## Step 4 — Login to GitHub

Check GitHub CLI:

```bash
gh --version
```

Login:

```bash
gh auth login
```

Select:

```text
GitHub.com
HTTPS
Yes
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

```bash
gh auth status
```

You should see that you are logged in to GitHub.

## Step 7 — Configure Git identity

Git needs your name and email for commits.

Set your name:

```bash
git config --global user.name "YOUR NAME"
```

Set your GitHub email:

```bash
git config --global user.email "YOUR_GITHUB_EMAIL"
```

Example:

```bash
git config --global user.name "smith ss"
git config --global user.email "smith@example.com"
```

Verify:

```bash
git config --global user.name
git config --global user.email
```

> Use an email associated with your GitHub account, or your GitHub `noreply` email if you don't want to expose your personal email.

## Step 8 — Check GitHub repository

```bash
git remote -v
```

If you see:

```text
origin  https://github.com/USERNAME/REPOSITORY.git (fetch)
origin  https://github.com/USERNAME/REPOSITORY.git (push)
```

your project is already connected to GitHub.

## Step 9 — Connect the repository if needed

If `git remote -v` shows nothing:

```bash
git remote add origin https://github.com/USERNAME/REPOSITORY.git
```

Example:

```bash
git remote add origin https://github.com/smithss/learn-with-me-kedro-azml.git
```

Then verify:

```bash
git remote -v
```

## Step 10 — Check your branch

```bash
git branch --show-current
```

If your branch is:

```text
main
```

continue using `main`.

## Step 11 — Get the latest code

Before starting work:

```bash
git pull origin main
```

## Step 12 — Check changes

```bash
git status
```

See detailed changes:

```bash
git diff
```

## Step 13 — Add changes

```bash
git add .
```

Check what will be committed:

```bash
git status
```

## Step 14 — Commit changes

```bash
git commit -m "Update project"
```

Example:

```bash
git commit -m "Add GitHub sync documentation"
```

## Step 15 — Push changes to GitHub

```bash
git push origin main
```

## Daily Workflow

### 1. Get latest code

```bash
git pull origin main
```

### 2. Work on the project

Make your code changes.

### 3. Check changes

```bash
git status
```

### 4. Add changes

```bash
git add .
```

### 5. Commit

```bash
git commit -m "Describe your changes"
```

### 6. Push

```bash
git push origin main
```

## Quick Version

For normal daily work:

```bash
git pull origin main

# Make changes

git status
git add .
git commit -m "Update project"
git push origin main
```

## First-Time Setup

If starting on a new Azure ML Compute Instance:

```bash
cd /mnt/batch/tasks/shared/LS_root/mounts/clusters/ci-house-price/code/Users/funoffun21/learn-with-me-kedro-azml

git config --global --add safe.directory /mnt/batch/tasks/shared/LS_root/mounts/clusters/ci-house-price/code/Users/funoffun21/learn-with-me-kedro-azml

gh auth login

git config --global user.name "YOUR NAME"
git config --global user.email "YOUR_GITHUB_EMAIL"

git remote -v
```

## Important — Do Not Commit Secrets

Never commit:

```text
.env
passwords
API keys
Azure credentials
access tokens
secrets
```

Before:

```bash
git add .
```

check:

```bash
git status
```

Make sure no secrets or sensitive files are being added.

## GitHub Sync Summary

```text
Azure ML Compute Instance
        |
        | git pull
        ↓
     GitHub
        |
        | git push
        ↑
Azure ML Compute Instance
```

The Compute Instance is your development environment.

GitHub is your source-code repository.
