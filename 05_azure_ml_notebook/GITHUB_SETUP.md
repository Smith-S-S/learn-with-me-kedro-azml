# Part 5b — Git & GitHub on the Azure ML Compute Instance

> Split out of `README.md` so the main Part 5 guide stays about Azure ML itself.
> **Read Part 5 sections A–E first** — you need a running compute instance and a
> terminal on it before any of this applies.
>
> Everything here is done **in the compute instance terminal**
> (ml.azure.com → **Notebooks** → the Terminal icon).

---

## The two-machine problem

You now have **two machines** — your Windows laptop and a Linux VM in Azure —
and the same project on both. Without a plan, this ends badly: you edit
`nodes.py` in Azure, edit it again on the laptop, and neither copy is right.

Git is that plan. The repo is the single source of truth; both machines are just
places you happen to be typing.

```
        ┌──────────────────────────┐
        │  GitHub / Azure Repos    │   ← the "parent" repo, the real one
        └───────┬──────────┬───────┘
           pull │          │ pull
           push │          │ push
        ┌───────▼───┐  ┌───▼──────────────┐
        │ your      │  │ Azure ML         │
        │ laptop    │  │ compute instance │
        └───────────┘  └──────────────────┘
```

Neither machine talks to the other. **Both talk to the repo.**

### 1. Tell git who you are (do this first, or the commit fails)

The compute instance is a fresh Linux box — git has never heard of you:

```bash
git config --global user.name  "Your Name"
git config --global user.email "you@company.com"
git config --global init.defaultBranch main
```

> Skip this and your first `git commit` stops with
> *"Please tell me who you are"*. Use the **same email as your GitHub / Azure
> DevOps account**, or your commits won't be linked to your profile.

⚠️ This config lives in `~/.gitconfig` on the instance's **local disk**. Stop and
start the instance and it's still there. **Delete and recreate** the instance and
it's gone — you'll redo this. (Same applies to SSH keys, below.)

### 2. Authentication — the part that actually trips people up

You cannot push with a password. GitHub removed password authentication years
ago; Azure DevOps is the same. You need **one of these two**:

| | **HTTPS + PAT** | **SSH key** |
|---|---|---|
| What it is | A long generated token used as your password | A key pair; the public half goes to GitHub |
| Setup effort | Lower — copy one token | A few more steps |
| Expires? | **Yes** — you'll redo this | No |
| Microsoft's docs recommend | Either | **This one** |
| Best for | A quick try | Working on Azure regularly |

Pick one. Both are covered below.

#### Route A — SSH key (recommended, and what Microsoft documents)

**1. Generate the key on the compute instance:**
```bash
ssh-keygen -t ed25519 -C "you@company.com"
```
When it asks where to save, **accept the default** `/home/azureuser/.ssh/id_ed25519`.

> 📌 **Do NOT move this into `~/cloudfiles/`.** SSH refuses to use a private key
> that other people could read, and the cloudfiles share is a mounted Azure file
> share where Linux permissions don't behave normally. Keys belong in `~/.ssh`.

Adding a passphrase is more secure but means typing it on every push. For a
learning instance, empty is a reasonable trade-off — for a work instance, use one.

**2. Copy the PUBLIC half** (`.pub` — never the other file):
```bash
cat ~/.ssh/id_ed25519.pub
```
Copy the whole line, starting `ssh-ed25519 AAAA...`.

> The file **without** `.pub` is your private key. It never leaves the machine
> and never gets pasted anywhere. If you ever paste it somewhere, regenerate it.

**3. Add it to your git service:**

| Service | Where |
|---|---|
| **GitHub** | Settings → SSH and GPG keys → **New SSH key** |
| **Azure DevOps** | User settings → **SSH public keys** → New Key |
| **GitLab** | Preferences → SSH Keys |

**4. Clone using the SSH URL** (starts with `git@`, not `https://`):
```bash
cd ~/cloudfiles/code/Users/$USER
git clone git@github.com:yourname/house-price.git
cd house-price
```

The first connection asks you to confirm a fingerprint — type `yes`. That's SSH
checking it's really talking to GitHub, not an impostor. It only asks once.

#### Route B — HTTPS + Personal Access Token

**1. Create the token:**

| Service | Where | Scope needed |
|---|---|---|
| **GitHub** | Settings → Developer settings → Personal access tokens | `repo` |
| **Azure DevOps** | User settings → Personal access tokens | **Code (Read & Write)** |

**Copy it immediately** — you're shown it exactly once.

**2. Clone normally, and paste the token when asked for a password:**
```bash
cd ~/cloudfiles/code/Users/$USER
git clone https://github.com/yourname/house-price.git
# Username: your-username
# Password: <paste the PAT -- not your real password>
```

**3. So you're not asked every single time:**
```bash
git config --global credential.helper 'cache --timeout=28800'   # 8 hours, in memory
```

> ⚠️ You'll also see `credential.helper store` suggested. **Avoid it here** — it
> writes your token to `~/.git-credentials` in **plain text**. On a shared
> workspace that's a real leak. `cache` keeps it in memory only.

### 3. Where to clone: `cloudfiles` or local disk?

This is an Azure-specific decision with a genuine trade-off, and it's documented
by Microsoft:

| | `~/cloudfiles/code/Users/<you>/` | `~/house-price` (local disk) |
|---|---|---|
| Survives **stop/start** | ✅ | ✅ |
| Survives **delete + recreate** | ✅ **kept** | ❌ **lost** |
| Visible in the Notebooks tab | ✅ | ❌ |
| Shared across instances | ✅ | ❌ |
| Speed | Slower (network file share) | **Faster** |

**Recommendation for you: use `~/cloudfiles/code/Users/$USER/`.** You get the
Notebooks tab, and nothing is lost if the instance is recreated. Since
everything important is pushed to git anyway, the loss risk is small either way —
but the file share is the safer habit while learning.

> If git feels sluggish on cloudfiles with a big repo, that's the network file
> share, not git. Cloning to the local disk is the documented fix — just push
> often, because that copy dies with the instance.

### 4. The everyday loop: change on Azure, push to the parent repo

You edit `nodes.py` in the Azure ML notebook editor. Now get it home:

```bash
cd ~/cloudfiles/code/Users/$USER/house-price

git status                    # what did I change? ALWAYS look first
git diff                      # show the actual line-by-line changes

git add src/house_price/pipelines/house_price_pipeline/nodes.py
# or stage everything that changed:  git add -A

git commit -m "Add mlflow metric logging to evaluate_model"

git pull --rebase origin main   # get others' work FIRST (see below)
git push origin main
```

#### Why `git pull --rebase` before pushing
If someone changed the repo since you cloned, your push is **rejected** — git
refuses to silently overwrite their work. Pulling first brings their commits
down; `--rebase` replays yours on top, giving a clean straight line instead of a
messy merge bubble.

If you skip it, you get:
```
! [rejected] main -> main (fetch first)
```
That error is not a problem — it's git protecting someone else's work. Pull, then push.

#### Going the other way (laptop → Azure)
On the compute instance, before you start work:
```bash
git pull origin main
```
**Make this the first thing you type** every time you open the terminal.
Most "why is my change gone?" confusion is really two machines that drifted apart.

### 5. What must never be committed

Your repo is about to be reachable from a cloud VM. Check `.gitignore` covers:

```gitignore
# Secrets -- the one that actually matters
conf/local/
credentials.yml
.env
*.pem
*.key

# Environments (Windows binaries, useless on Linux, and huge)
.venv/
__pycache__/

# Regenerated outputs
data/06_models/
data/08_reporting/
drift_report.html

# Notebook noise
.ipynb_checkpoints/
```

Two Azure-specific warnings:

1. **`conf/local/credentials.yml` must never be committed.** Once a secret is in
   git history, deleting the file later does **not** remove it — it lives in
   every clone forever. If it happens, treat the secret as leaked and rotate it.
2. **Notebooks store their output inside the `.ipynb` file.** A cell that printed
   a connection string or a customer row commits that data too. Clear outputs
   before committing (**Kernel → Restart & Clear Output**), or use `nbstripout`.

### 6. Why this matters for Part 7's jobs

Here's the payoff, and it connects the two parts.

When you submit an Azure ML job from inside a git repo, **Azure automatically
records where the code came from**:

| Property | What it stores |
|---|---|
| `azureml.git.repository_uri` | Which repo |
| `azureml.git.branch` | Which branch |
| `azureml.git.commit` | **The exact commit hash that ran** |
| `azureml.git.dirty` | `True` if you had **uncommitted changes** |

You get this for free — no configuration. And it's the missing half of Part 7's
"jobs are the record": the job now records not just *that* it ran, but
***exactly which version of the code*** ran.

```bash
az ml job show --name <job-name> --query "properties.\"azureml.git.commit\""
```

> 🎯 **The habit worth forming: commit before you submit a job.**
> Submit with uncommitted edits and Azure marks the run `azureml.git.dirty: True`
> — an honest flag meaning *"the recorded commit is not what actually ran."*
> That run can never be reproduced, which defeats the point of using jobs at all.


---

## Quick-reference (the whole workflow in one box)

```bash
# --- one-time, on a fresh compute instance ---
git config --global user.name  "Your Name"
git config --global user.email "you@company.com"
ssh-keygen -t ed25519 -C "you@company.com"      # accept /home/azureuser/.ssh/
cat ~/.ssh/id_ed25519.pub                        # paste into GitHub/Azure DevOps

# --- get the project ---
cd ~/cloudfiles/code/Users/$USER
git clone git@github.com:yourname/house-price.git
cd house-price

# --- every time you sit down ---
git pull origin main

# --- every time you finish something ---
git status                       # look before you leap
git add -A
git commit -m "what changed and why"
git pull --rebase origin main    # take others' work first
git push origin main
```

| Problem | What it means |
|---|---|
| `Please tell me who you are` | You skipped `git config user.name/user.email` (step 1) |
| `Authentication failed` (HTTPS) | Your PAT expired, or you typed your real password instead of the token |
| `Permission denied (publickey)` | The public key isn't on your git account, or you used the `https://` URL with an SSH setup |
| `! [rejected] ... (fetch first)` | Someone else pushed first. Run `git pull --rebase origin main`, then push. Not an error — it's git protecting their work. |
| Changes vanished after recreating the instance | You worked outside `~/cloudfiles/` **and** never pushed. The local disk is wiped on delete. |
| `git push` asks for a password every time | Set `git config --global credential.helper 'cache --timeout=28800'` |
| Key rejected, "permissions are too open" | The private key is on the `cloudfiles` share. Move it to `~/.ssh/`. |
