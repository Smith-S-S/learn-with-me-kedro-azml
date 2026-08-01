# Part 4 — Kubernetes & AKS (Beginner's Guide)

> Goal of this part: understand **what Kubernetes is**, **why anyone bothers**,
> and **how our house-price Kedro project would run on it** in Azure.
> Reading + a small optional hands-on. Nothing here is required for Part 5.

---

## A) Start from the problem, not the tool

Right now you run your Kedro pipeline like this:

```bash
python -m kedro run
```

It works — on **your laptop**, with **your** Python 3.12, **your** installed
packages. Three problems show up the moment other people or servers get involved:

| Problem | Real-world version of it |
|---|---|
| "Works on my machine" | Colleague has Python 3.9 → your code crashes |
| "Who restarts it?" | Server reboots at 3 AM, your job never comes back |
| "It's too slow / too big" | One machine isn't enough, you need 5 copies |

Two tools solve these, in order:

1. **Docker** solves *"works on my machine"* → it packs your code **and** Python
   **and** the libraries into one sealed box called a **container**.
2. **Kubernetes** solves *"who runs and restarts and scales those boxes"*.

So: **Docker = the box. Kubernetes = the person who manages thousands of boxes.**
(Docker gets its own full part later — Part 7. Here you only need the idea "a
container is a sealed box that runs my code the same way everywhere".)

---

## B) What is Kubernetes, in plain words

**Kubernetes** (often written **K8s** — K, then 8 letters, then s) is a program
that runs on a group of computers and answers one question all day:

> *"Are the containers the user asked for actually running right now? If not, fix it."*

You never tell Kubernetes **how** to do things. You write down **what you want**
("I want 3 copies of this container running, always") in a small text file, hand
it over, and Kubernetes keeps making reality match your text file. That style has
a name: **declarative** (you declare the desired end state; the system figures out
the steps).

If a container crashes → Kubernetes starts a new one.
If a whole machine dies → Kubernetes moves the containers to a healthy machine.
If you edit "3 copies" to "10 copies" → Kubernetes creates 7 more.

---

## C) The 6 words you actually need

| Word | Simple meaning | Analogy |
|---|---|---|
| **Cluster** | The whole group of machines Kubernetes manages | The whole factory |
| **Node** | One machine (a VM) inside the cluster | One worker in the factory |
| **Pod** | The smallest unit K8s runs — usually **1 container** | One sealed box on a worker's desk |
| **Deployment** | "Keep N copies of this pod alive forever" | Standing order for a web app |
| **Job** | "Run this pod **once**, until it finishes successfully" | A one-off task |
| **CronJob** | "Run this Job on a schedule" (e.g. daily 2 AM) | A recurring calendar reminder |

**Why "Pod" and not just "container"?** Because occasionally you need 2 containers
glued together (your app + a small helper that ships its logs). They must live on
the same machine and share a network. That glued group is a Pod. 95% of the time a
Pod = 1 container, so you can think of them as the same thing for now.

**Important for us:** our Kedro pipeline is **not** a website that runs forever.
It starts, trains a model, prints R², and **exits**. So the right object for us is
a **Job** (or a **CronJob** for "retrain every night"), *not* a Deployment.
Beginners almost always reach for Deployment and then wonder why Kubernetes keeps
restarting their finished training job — this is that trap, avoided.

---

## D) Benefits (and the honest costs)

**Benefits**
- **Self-healing** — crashed containers are replaced automatically.
- **Scaling** — one number in a file turns 1 copy into 50.
- **Same everywhere** — dev, test, prod all run the identical container image.
- **Scheduled work** — CronJob gives you "retrain the model nightly" for free.
- **Portable** — the same YAML runs on Azure (AKS), AWS, Google, or on-prem.
- **Rolling updates** — new version replaces the old one gradually, no downtime.

**Honest costs — read this before you `az aks create`**
- **It costs real money.** The AKS *control plane* is free on the Free tier, but
  every **node** is a VM you pay for by the hour, whether it's busy or idle.
  One small node ≈ a few dollars a day. **Delete your cluster when done.**
- **It is genuinely complex.** YAML, networking, permissions, storage.
- **It is overkill for one small pipeline.** For our house-price project, Azure ML
  (Part 5) or a plain container is simpler. Kubernetes earns its keep when you run
  *many* services, *continuously*, at *scale*, or when your company has standardised
  on it — which is exactly why you're learning it.

---

## E) What is AKS?

**AKS = Azure Kubernetes Service** — Microsoft's *managed* Kubernetes.

"Managed" means Microsoft runs the hard part (the **control plane**: the brain
that makes all the scheduling decisions), patches it, and keeps it alive. You only
manage the **nodes** where your containers actually run. Without AKS you would
install and babysit Kubernetes yourself, which is a full-time job.

```
   You write YAML  ──►  AKS control plane (Microsoft runs this, free)
                             │  decides where things go
                             ▼
                    Nodes = VMs (you pay for these)
                             │
                             ▼
                    Pods = your containers running
```

---

## F) How our project would run on AKS — the shape of it

Five steps. Steps 1–2 belong to Part 7 (Docker) and Part 8 (registry), so here we
only *name* them so the picture is complete:

1. **Build** a container image of the Kedro project (a `Dockerfile` — Part 7).
2. **Push** that image to **ACR** (Azure Container Registry, your private image
   storage — Part 7/8).
3. **Create** an AKS cluster and let it read from your ACR.
4. **Apply** a Job/CronJob YAML that says "run this image".
5. **Watch** the logs; the Job finishes and reports success.

---

## G) The YAML files (in this folder)

Two ready-to-read manifests are saved next to this README:

- [`kedro-job.yaml`](kedro-job.yaml) — run the pipeline **once**.
- [`kedro-cronjob.yaml`](kedro-cronjob.yaml) — run it **every night at 2 AM**.

Read `kedro-job.yaml` now — every line is commented. YAML is just a text format
for nested key/value data; indentation (**spaces only, never tabs**) shows nesting.

---

## H) Optional hands-on (⚠️ this one costs money)

Everything in Part 3 was free. This is not. Total cost if you finish in an hour
and delete: roughly a cup of coffee. Skip it guilt-free if you'd rather just read.

```bash
# 0) kubectl = the command-line tool for talking to Kubernetes.
#    "cube-control" or "cube-cuttle" — nobody agrees on the pronunciation.
az aks install-cli          # installs kubectl for you (may need admin on Windows)

# 1) A folder to hold everything, so cleanup is one command later
az group create --name rg-k8s-demo --location centralindia

# 2) The cluster. --node-count 1 = one VM. Smallest sane size. ~5-10 minutes.
az aks create \
  --resource-group rg-k8s-demo \
  --name aks-demo \
  --node-count 1 \
  --node-vm-size Standard_B2s \
  --generate-ssh-keys
```

# gg not have Standard_B2s
# Azure VM Sizes Available in Central India (B2 Series)

| VM Size | CPU Cores | RAM (GB) | Max Data Disk Count | OS Disk Size (MB) | Resource Disk Size (MB) |
|---------|-----------|----------|---------------------|-------------------|-------------------------|
| Standard_B2als_v2 | 2 | 4 GB | 4 | 1047552 | 0 |
| Standard_B2as_v2 | 2 | 8 GB | 4 | 1047552 | 0 |
| Standard_B2ats_v2 | 2 | 1 GB | 4 | 1047552 | 0 |
| Standard_B2ms | 2 | 8 GB | 4 | 1047552 | 16384 |
| Standard_B2s | 2 | 4 GB | 4 | 1047552 | 8192 |
| Standard_B20ms | 20 | 80 GB | 32 | 1047552 | 163840 |
| Standard_B2pls_v2 | 2 | 4 GB | 4 | 1047552 | 0 |
| Standard_B2ps_v2 | 2 | 8 GB | 4 | 1047552 | 0 |
| Standard_B2pts_v2 | 2 | 1 GB | 4 | 1047552 | 0 |
| Standard_B2ls_v2 | 2 | 4 GB | 4 | 1047552 | 0 |
| Standard_B2s_v2 | 2 | 8 GB | 4 | 1047552 | 0 |
| Standard_B2ts_v2 | 2 | 1 GB | 4 | 1047552 | 0 |

---

# Smallest VM Options

The smallest available VM sizes are:

| VM Size | CPU Cores | RAM |
|---|---:|---:|
| Standard_B2ats_v2 | 2 | 1 GB |
| Standard_B2pts_v2 | 2 | 1 GB |
| Standard_B2ts_v2 | 2 | 1 GB |

---

# Recommended AKS Learning Cluster

Although the 1 GB machines are the smallest, they are not recommended for Kubernetes because AKS itself needs memory for system components.

Recommended minimum:

| VM Size | CPU | RAM | Reason |
|---|---:|---:|---|
| Standard_B2ls_v2 | 2 cores | 4 GB | Lowest practical AKS option |
| Standard_B2s_v2 | 2 cores | 8 GB | Better experience for learning |

## Selected VM

For a low-cost AKS learning cluster:

```bash
--node-vm-size Standard_B2ls_v2
```

For a smoother Kubernetes experience:

```bash
--node-vm-size Standard_B2s_v2
```

# 2.1) So I choose Standard_B2s_v2, create cluster. --node-count 1 = one VM. Smallest sane size. ~5-10 minutes.

```bash
az aks create \
  --resource-group rg-k8s-demo \
  --name aks-demo \
  --node-count 1 \
  --node-vm-size Standard_B2s_v2 \
  --generate-ssh-keys

```

# 3) Download the cluster's credentials into kubectl's config file
```bash
az aks get-credentials --resource-group rg-k8s-demo --name aks-demo
```

# 4) Prove it works — you should see one node, STATUS "Ready"
```bash
kubectl get nodes
```

Now run something (a public test image, no Docker knowledge needed yet):

```bash
kubectl create job hello --image=mcr.microsoft.com/azuredocs/aci-helloworld
kubectl get pods                 # watch it go Pending -> Running -> Completed
kubectl logs job/hello           # see its output
kubectl describe job hello       # full detail if something looks wrong
```

Once you have your own image in ACR (Part 7), the *only* change is the image name
in `kedro-job.yaml`, then:

```bash
kubectl apply -f kedro-job.yaml   # "make reality match this file"
kubectl get jobs
kubectl logs job/kedro-house-price
kubectl delete -f kedro-job.yaml  # remove it
```

### 🧹 Cleanup — do not skip this
```bash
az group delete --name rg-k8s-demo --yes --no-wait
```
Deleting the resource group deletes the cluster, the nodes, the disks — the whole
folder. This is the single most important habit in Azure: **one resource group per
experiment, delete the group when finished.** Verify with `az group list -o table`.

---

## I) Everyday kubectl cheat sheet

| Command | What it does |
|---|---|
| `kubectl get nodes` | List the machines in the cluster |
| `kubectl get pods` | List running containers |
| `kubectl get jobs` | List one-off tasks |
| `kubectl get all` | Everything in the current namespace |
| `kubectl logs <pod>` | Print a pod's output |
| `kubectl logs -f <pod>` | Follow the output live (like `tail -f`) |
| `kubectl describe pod <pod>` | Why is it stuck? Events are at the bottom |
| `kubectl apply -f file.yaml` | Create/update from a file |
| `kubectl delete -f file.yaml` | Delete what that file created |
| `kubectl exec -it <pod> -- bash` | Open a shell *inside* a running container |

> `-f` means "from this file". `-it` means "interactive terminal".
> A **namespace** is just a folder inside the cluster to keep names from clashing;
> you're in the one called `default` and can ignore it for now.

---

## J) Two-line summary

**Kubernetes** keeps containers running the way you declared, restarts them when
they fail, and scales them on demand. **AKS** is Azure running Kubernetes' brain
for you so you only pay for and worry about the worker machines.

---

## Next up (Part 5)
**Azure ML Notebook** — creating an Azure Machine Learning workspace, spinning up a
compute instance, and running this exact Kedro project *in the cloud* from a
browser notebook. Much cheaper and much simpler than AKS, and the natural next
home for our pipeline.
