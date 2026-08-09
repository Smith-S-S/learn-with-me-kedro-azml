# Part 9 — Azure Artifacts: installing Python libraries from a private feed

In Part 8 our Dockerfile ran `pip install -r requirements.txt`. That reaches out
to **pypi.org — the open internet** — and downloads code written by strangers,
straight into a container your company will run.

This part replaces that with your organization's **own scanned package feed**.

---

## Why companies refuse to let builds touch public PyPI

`pip install pandas` looks harmless. Here is what it actually is: **you are
downloading and running someone else's code, automatically, with no review.**
And pandas pulls in its own dependencies, which pull in theirs. One `pip
install` can execute code from dozens of authors you've never heard of.

That chain is called the **software supply chain**, and it is attacked in four
main ways:

| Attack | How it works |
|---|---|
| **Typosquatting** | Attacker publishes `panda` (no *s*), or `requsts`. One typo and you install their code instead. |
| **Dependency confusion** | Attacker publishes a package with your *internal* name at a huge version number. Your build picks it up. Explained in full below. |
| **Account takeover** | A real, popular package's maintainer account is stolen and a malicious update is published. Everyone who upgrades is hit. |
| **Availability** | A package is deleted or PyPI is down, and your build simply stops working. This has happened and broken large parts of the internet. |

A private feed fixes all four, for one simple reason: **nothing enters the
company without passing through a place your security team controls.**

---

## What Azure Artifacts is

**Azure Artifacts** is a private package store inside Azure DevOps. Think of it
as your company's own PyPI.

> **Analogy: a company library.**
> Anyone can buy any book on the open market. But your company library only
> stocks books a librarian has checked. Staff borrow from the library, not from
> random street sellers. If a book turns out to be dangerous, the librarian
> pulls it from one shelf and nobody can borrow it again.

### The key idea: upstream sources
The obvious worry is: *"if we can only use the private feed, how do we install
pandas — which lives on public PyPI?"*

The answer is the feature that makes this practical. A feed can have an
**upstream source** pointing at public PyPI:

```
   Your build
       |  pip install pandas
       v
 [ Azure Artifacts feed ]
       |  "I don't have pandas cached yet."
       v
   [ public PyPI ]  ---- downloads it once ----> feed SAVES A COPY
       |
       v
   Your build gets pandas -- from the feed
```

So:
- **First time** anyone asks for `pandas`, the feed fetches it from PyPI and
  **keeps a copy forever.**
- **Every time after that**, it's served from the feed — faster, and it still
  works if PyPI is down or the package is deleted.
- Your security team can scan and **block** specific packages or versions.
- Internal packages live in the same feed alongside public ones.

You get the convenience of PyPI with a controlled gate in front of it.

---

## ⚠️ The one thing to get right: `index-url`, not `extra-index-url`

This is the most important section in this part. It is a real attack that has
succeeded against very large companies.

### The mistake
Most tutorials tell you to add your feed like this:

```ini
extra-index-url = https://pkgs.dev.azure.com/myorg/_packaging/my-feed/pypi/simple/
```

`extra-index-url` means: *"check the private feed **and also** public PyPI, then
install whichever has the **highest version number**."*

### Why that's dangerous

1. Your company has an internal package `houseprice-utils`, version `1.2.0`,
   which exists **only** in your private feed.
2. An attacker learns that name. This is easy — it leaks through job adverts,
   public Dockerfiles, GitHub issues, conference talks, stack traces.
3. They upload their **own** `houseprice-utils` to **public PyPI**, version
   `99.0.0`, containing whatever code they want.
4. Your build runs `pip install houseprice-utils`. pip checks both sources, sees
   `99.0.0 > 1.2.0`, and installs **the attacker's package**.

Nobody typed anything wrong. Nothing looks broken. The build goes green.

This is **dependency confusion**.

### The fix
Use **`index-url`** — one single source of truth:

```ini
[global]
index-url = https://pkgs.dev.azure.com/myorg/_packaging/my-feed/pypi/simple/
```

Now the feed answers **every** request. Public packages still work, because the
upstream source fetches them. But an internal name can never be silently
overridden by a public one, because pip never talks to PyPI directly.

> **Remember it this way:**
> `extra-index-url` = "ask around and take the best offer." ❌
> `index-url` = "ask exactly one trusted source." ✅

---

## Files in this folder

| File | What it does |
|---|---|
| `pip.conf` | Points pip at the private feed (`index-url` only) |
| `azure-pipelines-artifacts.yml` | A CI pipeline that authenticates and builds |

---

## Hands-on

### 1. Create the feed
Azure DevOps → **Artifacts** → **Create Feed**

| Setting | Choose | Why |
|---|---|---|
| Name | `my-python-feed` | You'll use this in URLs |
| Visibility | Your organization | Not public |
| Upstream sources | ✅ **Enable** | So public packages still work |
| Scope | Organization or Project | Organization if several projects share it |

Or from the CLI:
```bash
az artifacts universal publish --help    # check the extension is installed

az devops configure --defaults organization=https://dev.azure.com/myorg
```

### 2. Point pip at it locally
Copy `pip.conf` to the right place for your OS and edit the org/feed names:

```bash
# Windows
copy pip.conf %APPDATA%\pip\pip.ini

# Linux / macOS
mkdir -p ~/.pip && cp pip.conf ~/.pip/pip.conf
```

### 3. Authenticate
Your laptop needs to prove who it is. The friendly way:

```bash
pip install keyring artifacts-keyring
```

`artifacts-keyring` pops up a browser login the first time you install
something, then remembers it. **This is the recommended path** — no tokens to
copy, paste, or accidentally commit.

The manual alternative is a **PAT** (Personal Access Token) — a long password
you generate in Azure DevOps with *Packaging: Read* scope:

```
https://<anything>:<YOUR-PAT>@pkgs.dev.azure.com/myorg/_packaging/my-python-feed/pypi/simple/
```

> ⚠️ A PAT in a URL ends up in `pip.conf`, shell history, and eventually a git
> commit. If you must use one, set an expiry and never commit the file.
> Prefer `artifacts-keyring` locally, and pipeline authentication in CI.

### 4. Test it
```bash
pip install pandas -v
```
The `-v` output shows which URL pip contacted. You want to see
`pkgs.dev.azure.com`, **not** `pypi.org`. That one line is your proof it worked.

### 5. Use it in CI
See `azure-pipelines-artifacts.yml`. The essential step is:

```yaml
- task: PipAuthenticate@1
  inputs:
    artifactFeeds: 'my-python-feed'
    onlyAddExtraIndex: false     # <-- keep false; true reopens the attack above
```

## *2. Point `pip` at the Azure Artifacts feed from the Compute Instance

We will configure `pip` **inside the compute instance only**. Your personal/laptop Python configuration does not need to be changed.

Your Azure Artifacts feed is:

`house-price` project → `my-python-feed`

### If your Compute Instance is Linux

Open the terminal of the compute instance and run:

```bash
mkdir -p ~/.pip
nano ~/.pip/pip.conf
```

Add:

```ini
[global]
index-url = https://pkgs.dev.azure.com/funoffun21/house-price/_packaging/my-python-feed/pypi/simple/
timeout = 60
retries = 3
```

Save the file.

You can check that it was created with:

```bash
cat ~/.pip/pip.conf
```

From now on, `pip` running **inside this compute instance** will know that the Azure Artifacts feed is its package source.

> **Important:** This only configures `pip` inside this compute instance. It does not change the `pip` configuration on your personal computer.

---

## 3. Authenticate from the Compute Instance

The feed is private, so the compute instance needs permission to access it.

Install the Azure Artifacts credential helper:

```bash
pip install keyring artifacts-keyring
```

Then try installing a package from the feed:

```bash
pip install pandas -v
```

If authentication is required, `artifacts-keyring` can handle Azure DevOps authentication.

If your compute environment cannot open a browser, use the authentication method provided by your organization's Azure DevOps setup rather than putting a PAT directly into the `pip.conf` URL.

### Avoid putting a PAT in `pip.conf`

Do **not** normally put this:

```text
https://anything:YOUR-PAT@pkgs.dev.azure.com/...
```

into `pip.conf`.

A PAT can end up in configuration files, shell history, logs, or Git commits.

---

## 4. Test the connection

From the **compute instance terminal**, run:

```bash
pip install pandas -v
```

Look through the output for:

```text
pkgs.dev.azure.com
```

This confirms that `pip` is using the Azure Artifacts feed.

You can also check the configuration with:

```bash
pip config list
```

You should see your Azure Artifacts `index-url`.

### Important

Because we are using:

```ini
index-url = https://pkgs.dev.azure.com/funoffun21/house-price/_packaging/my-python-feed/pypi/simple/
```

the Azure feed is the main package source.

There is deliberately no:

```ini
extra-index-url
```

---

## 5. Use the feed in CI

For Azure Pipelines, authentication should be handled by the pipeline rather than by copying your local credentials into the repository.

Use:

```yaml
- task: PipAuthenticate@1
  inputs:
    artifactFeeds: 'house-price/my-python-feed'
    onlyAddExtraIndex: false
```

This authenticates the pipeline to the Azure Artifacts feed.

Your repository should **not** contain your personal PAT or credentials.

---

## 6. The complete flow

The setup now looks like this:

```text
Your Compute Instance
        │
        │ pip install ...
        ↓
   ~/.pip/pip.conf
        │
        │
        ↓
Azure DevOps
funoffun21
    │
    └── house-price
          │
          └── my-python-feed
                    │
                    ↓
             Python packages
```

### In simple terms

**Compute instance:**

```bash
pip install my-company-package
```

↓

`pip` reads:

```text
~/.pip/pip.conf
```

↓

It knows to use:

```text
funoffun21 / house-price / my-python-feed
```

↓

Azure DevOps checks authentication.

↓

If you have permission, the package is downloaded and installed.

---

### Your Azure Artifacts feed

[Open the my-python-feed feed in Azure DevOps](https://dev.azure.com/funoffun21/house-price/_artifacts/feed/my-python-feed?utm_source=chatgpt.com)


**Why this step is needed at all:** the build agent is a brand new machine that
has never logged into anything. Without it you get `401 Unauthorized`, and the
error doesn't obviously point at the missing auth step.

Notice there is **no password anywhere in the YAML.** Azure DevOps already knows
who the pipeline is and issues a short-lived token itself.

### 6. Use it inside the Docker build
The Docker build runs in its own sealed environment, so it does **not** inherit
the agent's authentication. Use a build-time secret:

```dockerfile
RUN --mount=type=secret,id=pipconf,target=/etc/pip.conf \
    pip install --no-cache-dir -r requirements.txt
```
```bash
docker build --secret id=pipconf,src=pip.conf -t house-price-api:1.0 .
```

**Why not just `COPY pip.conf` into the image?** Because the token would be
baked into an image layer permanently. Deleting the file in a later step does
**not** remove it — the earlier layer still contains it, and anyone who pulls
the image can extract it. A `--mount` secret exists only during that one command
and is never written to any layer.

---

## Publishing your OWN package to the feed

Internal shared code — say `houseprice-utils` — goes in the same feed:

```bash
pip install build twine
python -m build                      # creates dist/*.whl and dist/*.tar.gz
twine upload -r my-python-feed dist/*
```

Then teammates just `pip install houseprice-utils`, exactly like any public
package. This is how companies share code without publishing it to the world.

---

## Common problems

| What you see | What it means |
|---|---|
| `401 Unauthorized` | Not authenticated. Locally: install `artifacts-keyring`. In CI: you skipped `PipAuthenticate@1`. |
| `403 Forbidden` | Authenticated, but your account lacks *Packaging: Read* on the feed. |
| `Could not find a version that satisfies...` | Upstream sources are off, so the feed has no route to public PyPI. Turn them on. |
| Works locally, `401` in Docker build | The build environment doesn't inherit your auth. Use `--mount=type=secret`. |
| Works locally, fails in CI | Your laptop still has a `pip.conf` with a PAT that the agent doesn't. |
| Installs are slow the first time | Expected — the feed is fetching and caching from upstream. It's fast afterwards. |

## 💸 Costs

| Thing | Cost |
|---|---|
| First **2 GiB** of Artifacts storage | **Free** |
| Beyond that | ~$2 per GiB/month |
| Upstream-cached packages | Count toward your storage |

Cheap, but not free forever — a feed that has cached years of every version of
every package does grow. Feeds support retention policies to clean up old
versions automatically.

---

## What you now understand
- `pip install` runs strangers' code; the **supply chain** is a real attack surface.
- **Azure Artifacts** is your company's private PyPI, with a security gate.
- **Upstream sources** let public packages through while caching a permanent copy.
- **`index-url`, never `extra-index-url`** — that one word is the difference
  between a controlled feed and a **dependency confusion** vulnerability.
- Authenticate with **`artifacts-keyring`** locally and **`PipAuthenticate@1`**
  in CI. Never commit a PAT.
- Use **`--mount=type=secret`** in Docker so credentials never land in a layer.

## Next up (Part 10)
**Putting it all together** — nine parts have given you nine working pieces that
aren't yet connected. Part 10 wires them into one running system: image → ACR →
AKS → APIM, with the trained model travelling from the pipeline to the API
through Azure Blob Storage.

Then **Part 11 (Entra ID)** issues the real tokens the APIM policy validates.
