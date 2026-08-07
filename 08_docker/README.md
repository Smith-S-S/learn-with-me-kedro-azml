# Part 8 — Docker: packaging the API so it runs anywhere

In Part 7 we ran the pipeline on Azure's machines, borrowing an environment
Microsoft maintains. But the API still only runs **on your laptop**, using
**your** Python and **your** installed libraries.

This part fixes the oldest complaint in software: *"but it works on my machine."*

---

## What a container actually is

### The problem
Your API works here because your laptop happens to have Python 3.12,
scikit-learn 1.7.1, pandas, FastAPI, and a dozen other things at exactly the
right versions. A colleague's machine has Python 3.10 and scikit-learn 1.4.

Their machine runs the same code and gets a different answer — or, more often, a
crash they'll spend an afternoon on. Multiply by a server, a test environment,
and a build agent, and this becomes most of the pain in software delivery.

### The fix
A **container** packages your code **together with** the exact Python version
and the exact library versions it needs. It is a sealed box: the same box runs
identically on your laptop, on a colleague's machine, in Azure, and in
Kubernetes — because the box brings its own everything.

> **Analogy: shipping containers.**
> Before them, cargo was loaded loose and every port needed different equipment.
> The steel container standardised the *outside* so any crane could lift it,
> while the *inside* could hold anything. Docker did that for software: the
> outside is standard, so any machine can run it; the inside is whatever your
> app needs.

### The three words people mix up

| Word | What it is | Everyday comparison |
|---|---|---|
| **Dockerfile** | The written recipe | A recipe on paper |
| **Image** | The built, frozen result | A cake you baked and froze |
| **Container** | A running copy of an image | The cake, out and being eaten |

One image can start **many** containers, all identical. That is what lets
Kubernetes run 10 copies of your API to handle traffic.

### Container vs virtual machine
Both isolate software, but a VM carries an entire second operating system —
gigabytes, and a minute to boot. A container **shares** the host's OS kernel and
adds only your app and its libraries. Megabytes, and it starts in under a second.

That speed is exactly why containers won: starting 10 more copies during a
traffic spike takes seconds, not minutes.

---

## The base image, and why `mcr.microsoft.com`

Every Dockerfile starts `FROM` something. You almost never begin from an empty
machine — you begin from one someone else already prepared with an OS and Python
installed. That is the **base image**.

Ours is:

```dockerfile
FROM mcr.microsoft.com/azurelinux/base/python:3.12
```

Read it in three pieces:

| Piece | Meaning |
|---|---|
| `mcr.microsoft.com` | **Where** it comes from — Microsoft Container Registry |
| `azurelinux/base/python` | **What** it is — Python on Azure Linux, Microsoft's own hardened OS |
| `:3.12` | **Which version** — the tag |

### Why MCR rather than Docker Hub?
This one matters in a corporate setting, and it's a question you'll be asked:

| Reason | The detail |
|---|---|
| **Patching** | Microsoft rebuilds these images when security fixes land. Random Docker Hub images may be years stale. |
| **Rate limits** | Docker Hub throttles anonymous pulls. A busy CI pipeline hits that limit and builds start failing at random. |
| **Firewalls** | Many corporate networks allow MCR and block Docker Hub entirely. |
| **Provenance** | You can point at Microsoft as the publisher during an audit. |

### Why not `:latest`?
`:latest` means "whatever is newest today." Your build silently changes
underneath you, and code that built fine last week fails today with no visible
cause. **Pin your versions.** For strict reproducibility, pin fully:

```dockerfile
FROM mcr.microsoft.com/azurelinux/base/python:3.12.9-9-azl3.0.20260304
```

---

## Layers, and the one trick that makes builds fast

Each instruction in a Dockerfile creates a **layer** — a saved snapshot. Docker
caches them. If nothing a layer depends on changed, Docker reuses the cache
instead of redoing the work.

This is why our Dockerfile does something that looks backwards:

```dockerfile
COPY requirements.txt .          # <-- copy ONLY this first
RUN pip install -r requirements.txt
COPY . .                         # <-- the actual code, afterwards
```

**Why:** installing libraries is slow (minutes). Your code changes constantly.
By installing *before* copying the code, editing `main.py` doesn't invalidate
the install layer — so rebuilds take seconds.

If you copied everything first, **every one-character code edit would reinstall
pandas and scikit-learn from scratch.** Same result, minutes wasted, every time.

> **Rule of thumb:** put the things that rarely change at the TOP of a
> Dockerfile, and the things that change constantly at the BOTTOM.

## Multi-stage builds

Our Dockerfile has two `FROM` lines. That's a **multi-stage build**:

1. **Stage 1 (`builder`)** — a full environment where we install the libraries.
2. **Stage 2 (`runtime`)** — a fresh, clean image where we copy **only the
   finished virtual environment** across.

Compilers, pip's cache, and build tools stay behind in stage 1 and never ship.

**Why bother?** A smaller image downloads faster — but more importantly, every
extra tool inside an image is another thing an attacker could use if they get
in. A container with no compiler is a container where an attacker can't compile
anything.

---

## The files in this folder

| File | What it does |
|---|---|
| `Dockerfile` | The recipe. Fully commented, line by line. |
| `.dockerignore` | What to keep OUT of the image (`.venv`, secrets, data) |
| `docker-compose.yml` | Run it all with one command |

**Copy all three into `house-price/`** — a Dockerfile has to sit with the code
it packages:

```bash
copy 08_docker\Dockerfile      house-price\
copy 08_docker\.dockerignore   house-price\
copy 08_docker\docker-compose.yml house-price\
```

### `.dockerignore` deserves 30 seconds of your attention
It isn't just tidiness. It prevents a real bug and a real leak:

- **The bug:** `.venv/` holds **Windows** executables. Copying them into a Linux
  container produces a broken environment that fails in baffling ways. The image
  must install its own Linux libraries — which the Dockerfile does.
- **The leak:** `conf/local/credentials.yml` holds secrets. **Anyone who pulls
  your image can read every file inside it.** Secrets must be passed at *run*
  time as environment variables, never baked in at *build* time.

---

## Hands-on

> ⚠️ Docker Desktop must be **running**, not just installed. If you see
> `error during connect ... dockerDesktopLinuxEngine`, that's all this means —
> start Docker Desktop and wait for the whale icon to settle.

> 📌 **Honest note:** the base image tag
> `mcr.microsoft.com/azurelinux/base/python:3.12` was verified to exist in MCR,
> but this Dockerfile has **not been built** — Docker Desktop wasn't running on
> this machine. Expect to iterate once on the first build. The most likely spot
> is the `tdnf install shadow-utils` line: if your base image already has
> `useradd`, that line is harmless but unnecessary; if the package name differs
> in a newer Azure Linux, adjust it there.

### 1. Build the image
```bash
cd house-price
docker build -t house-price-api:1.0 .
```
- `-t` = "tag", i.e. name it. `house-price-api:1.0` is `name:version`.
- The `.` at the end means "build using this folder." Easy to forget.

### 2. Run it
```bash
docker run -p 8000:8000 house-price-api:1.0
```
`-p 8000:8000` connects port 8000 on your laptop to port 8000 in the container.
**Without `-p`, the API runs but you cannot reach it** — the container's ports
are sealed by default.

Test it exactly as before:
```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/predict ^
     -H "Content-Type: application/json" ^
     -d "{\"size_sqft\":2000,\"num_bedrooms\":3,\"age_years\":10}"
```
Expected: `{"predicted_price":465276.13,"currency":"USD"}` — the same number as
Part 1 and Part 2, now coming from inside a container.

### 3. Or use Compose (simpler)
```bash
docker compose up --build     # start
docker compose down           # stop
```

### 4. Useful commands while learning
```bash
docker ps                       # what is running right now
docker ps -a                    # including stopped ones
docker images                   # what images you have built
docker logs <container-id>      # see the app's output
docker exec -it <id> /bin/bash  # open a shell INSIDE the running container
docker system prune -a          # delete unused images (frees a LOT of disk)
```

`docker exec` is the one to remember for debugging — it puts you inside the
running box so you can look around and see what's really there.

---

## Pushing to ACR (Azure Container Registry)

**ACR is your company's private image store.** Docker Hub is public; ACR is
yours alone. Your organization will insist on it, because a public image can be
pulled by anyone and may leak internal details.

```bash
# 1. Create the registry (names must be globally unique, letters+numbers only)
az acr create --resource-group my-ml-rg --name mycompanyacr --sku Basic

# 2. Log in. This quietly hands Docker a token -- no password typing.
az acr login --name mycompanyacr

# 3. Tag the image with the registry address.
#    An image can only be pushed to the registry named in its own tag.
docker tag house-price-api:1.0 mycompanyacr.azurecr.io/house-price-api:1.0

# 4. Push
docker push mycompanyacr.azurecr.io/house-price-api:1.0

# 5. Check it arrived
az acr repository list --name mycompanyacr --output table
```

### The MCR → ACR pattern your organization uses
Many regulated companies don't let build machines reach the public internet at
all. Instead they **mirror** approved base images into ACR first:

```bash
# Pull an approved base image from MCR into your private ACR, once
az acr import --name mycompanyacr ^
  --source mcr.microsoft.com/azurelinux/base/python:3.12 ^
  --image base/python:3.12
```

Then every internal Dockerfile starts from the *private* copy:

```dockerfile
FROM mycompanyacr.azurecr.io/base/python:3.12
```

**Why:** the security team scans and approves that one image. Nothing enters the
company unreviewed, and builds keep working even if the internet is unreachable.
This is exactly the pattern behind Part 9's private Python feed — same idea, one
layer up.

---

## Common problems

| What you see | What it means |
|---|---|
| `error during connect ... dockerDesktopLinuxEngine` | Docker Desktop isn't running. Start it. |
| API runs but `localhost:8000` refuses | Missing `-p 8000:8000`, **or** you used `--host 127.0.0.1` instead of `0.0.0.0` in the CMD. |
| `COPY failed: file not found` | You forgot the `.` at the end of `docker build`, or the file is excluded by `.dockerignore`. |
| Image is enormous (1GB+) | `.venv/` or `data/` got copied in. Check `.dockerignore` is in the same folder as the Dockerfile. |
| `unauthorized` on push | Run `az acr login --name <registry>` again; tokens expire. |
| Works locally, crashes in container | Nearly always a missing entry in `requirements.txt` — your laptop has it installed globally, the container doesn't. |

## 💸 Costs and cleanup

| Thing | Cost |
|---|---|
| Docker Desktop (personal / small business) | Free |
| ACR **Basic** | ~$5/month |
| ACR Standard | ~$20/month |

```bash
az acr delete --name mycompanyacr --resource-group my-ml-rg --yes
docker system prune -a     # reclaim local disk
```

---

## What you now understand
- A **container** ships your code *with* its exact Python and libraries, so it
  runs the same everywhere.
- **Dockerfile** = recipe, **image** = frozen result, **container** = running copy.
- **Base images** come from **MCR** because it's patched, unthrottled, and
  firewall-friendly. Pin the version; never use `:latest`.
- **Layer caching** is why `requirements.txt` is copied before the code.
- **Multi-stage builds** leave build tools behind, making images smaller and safer.
- **ACR** is your private image store; `az acr import` mirrors approved bases.

## Next up (Part 9)
**Azure Artifacts** — right now `pip install` reaches out to the public
internet. Part 9 replaces that with your company's **private, scanned package
feed**, so no unreviewed code enters a build.
