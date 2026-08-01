# Part 3 — Azure Account + Azure CLI (Beginner's Guide)

## A) What is Azure, in one line?
Azure is Microsoft's **cloud**: instead of buying your own computers/servers, you
*rent* them from Microsoft's data centers and only pay for what you use.

## B) How to create an Azure account (walkthrough)
> You already have one (`funoffun21@gmail.com`), so this is just for understanding.

1. Go to **https://azure.microsoft.com/free**.
2. Click **"Start free"**. Sign in with a Microsoft account (or create one).
3. **Identity check**: you enter a phone number (SMS code) and a **credit/debit
   card**.
   - *Why a card if it's free?* Only to prove you're a real person. The free
     tier does **not** charge you; you must manually "upgrade" before anything
     bills you.
4. You get:
   - **$200 (approx) free credit** for 30 days, plus
   - A list of services that are **always free** or free for 12 months.
5. Done. You land in the **Azure Portal** (https://portal.azure.com) — the
   click-with-your-mouse website for managing Azure.

## C) Two ways to control Azure
| Way | What it is | Best for |
|-----|-----------|----------|
| **Portal** | The website, click buttons | Learning, seeing things visually |
| **Azure CLI** (`az`) | Type commands in a terminal | Repeatable, scriptable, automation |

We focus on the **CLI** because everything later (Docker, DevOps, pipelines) is
automated with commands, not mouse clicks.

## D) 4 words you'll hear constantly
| Word | Simple meaning |
|------|----------------|
| **Subscription** | Your "billing account" — where usage gets charged |
| **Resource** | Any single thing you create (a VM, a database, a storage box) |
| **Resource Group** | A *folder* that holds related resources together |
| **Region** | Which physical data-center location (e.g. `centralindia`) |

> A **Resource Group is free** — it's just a folder. You delete the folder and
> everything inside it is deleted together. Great for tidy experiments.

## E) The core beginner commands (your cheat sheet)

### Logging in
```bash
az login                 # opens a browser to sign in (do this first!)
az login --use-device-code   # if the browser way doesn't work
az account show          # who am I / which subscription is active
az logout                # sign out
```
> Tokens EXPIRE after a while. If you see "AADSTS50132 / session is not valid",
> just run `az login` again. That is normal, not a bug.

### Looking around (read-only, 100% safe)
```bash
az account list -o table            # all subscriptions you can use
az account list-locations -o table  # all regions
az group list -o table              # your resource groups (folders)
az version                          # CLI version + installed extensions
```

### Creating your first things (free/cheap)
```bash
# 1) Make a resource group (a free folder) in the Central India region
az group create --name rg-house-price --location centralindia

# 2) See it exists
az group show --name rg-house-price -o table

# 3) When finished, delete the folder AND everything in it
az group delete --name rg-house-price --yes --no-wait
```

### Handy output tricks
```bash
... -o table     # human-friendly table
... -o json      # full detail (default)
... -o tsv       # plain text, great for scripts
--query "..."    # filter results (uses a mini-language called JMESPath)
```
Example: just the names of your groups:
```bash
az group list --query "[].name" -o tsv
```

## F) A safe practice routine (try these in order)
```bash
az login
az account show -o table
az account list-locations --query "[?contains(name,'india')]" -o table
az group create --name rg-house-price --location centralindia
az group list -o table
# ... admire your work ...
az group delete --name rg-house-price --yes --no-wait   # optional cleanup
```

Nothing above costs money: login, listing, and an empty resource group are all
free. Charges only start when you put *real* resources (like a VM) inside a group.

## Next up (Part 4)
**Kubernetes** — what it is, why teams use it, its benefits, and how it fits our
project (via Azure's managed version, called **AKS**).
