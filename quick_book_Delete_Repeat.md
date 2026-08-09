# Azure ML — Delete Tonight & Recreate Tomorrow

## 🌙 Tonight — Delete Azure Resources

> ⚠️ This permanently deletes the Azure resources in the resource group. Make sure there is nothing in Azure that you need to keep.

### 1. Permanently delete the Azure ML workspace

```bash
az ml workspace delete \
  --name mlw-house-price \
  --resource-group rg-azureml-demo \
  --permanently-delete \
  --yes
```

### 2. Delete the entire resource group

```bash
az group delete \
  --name rg-azureml-demo \
  --yes \
  --no-wait
```

### 3. Check that the resource group is deleted

Run:

```bash
az group exists --name rg-azureml-demo
```

Expected:

```text
false
```

You can also check:

```bash
az group show --name rg-azureml-demo
```

It should eventually report that the resource group does not exist.

---

# ☀️ Tomorrow — Fresh Azure ML Setup

## 1. Login to Azure

```bash
az login
```

Check the active subscription:

```bash
az account show --query "{name:name,id:id}" -o table
```

---

## 2. Create the Resource Group

```bash
az group create \
  --name rg-azureml-demo \
  --location eastus
```

Verify:

```bash
az group show \
  --name rg-azureml-demo \
  -o table
```

---

## 3. Create the Azure ML Workspace

```bash
az ml workspace create \
  --name mlw-house-price \
  --resource-group rg-azureml-demo
```

Verify:

```bash
az ml workspace show \
  --name mlw-house-price \
  --resource-group rg-azureml-demo \
  -o table
```

---

## 4. Create the Compute Instance

```bash
az ml compute create \
  --name ci-house-price \
  --type ComputeInstance \
  --size Standard_D2_v3 \
  --workspace-name mlw-house-price \
  --resource-group rg-azureml-demo
```

Check the compute state:

```bash
az ml compute show \
  --name ci-house-price \
  --workspace-name mlw-house-price \
  --resource-group rg-azureml-demo \
  --query "state" \
  -o tsv
```

Expected:

```text
Running
```

---

# 🐍 Kedro + Azure ML

## 5. Activate the project environment

From the project directory:

```bash
source .venv/Scripts/activate
```

Check Kedro:

```bash
kedro info
```

---

## 6. Initialize Kedro Azure ML

```bash
kedro azureml init \
  --azure-subscription-id 1268fd42-f434-4927-a1a6-632642e6d7de \
  --resource-group rg-azureml-demo \
  --workspace-name mlw-house-price \
  --experiment-name house-price-training \
  --cluster-name ci-house-price
```

---

## 7. Run the Kedro Pipeline on Azure ML

```bash
kedro azureml run
```

---

# 🔎 Useful Verification Commands

### Check Azure subscription

```bash
az account show --query "{name:name,id:id}" -o table
```

### Check resource group

```bash
az group show \
  --name rg-azureml-demo \
  -o table
```

### Check workspace

```bash
az ml workspace show \
  --name mlw-house-price \
  --resource-group rg-azureml-demo \
  -o table
```

### Check compute

```bash
az ml compute show \
  --name ci-house-price \
  --workspace-name mlw-house-price \
  --resource-group rg-azureml-demo \
  --query "state" \
  -o tsv
```

### List jobs

```bash
az ml job list --output table
```

### Show a job

```bash
az ml job show --name <JOB_NAME>
```

### Stream a job

```bash
az ml job stream --name <JOB_NAME>
```

---

# 🧹 End of Day — Delete Again

When finished studying, delete the Azure resources again.

### Delete workspace

```bash
az ml workspace delete \
  --name mlw-house-price \
  --resource-group rg-azureml-demo \
  --permanently-delete \
  --yes
```

### Delete resource group

```bash
az group delete \
  --name rg-azureml-demo \
  --yes \
  --no-wait
```

### Confirm deletion

```bash
az group exists --name rg-azureml-demo
```

Expected:

```text
false
```

---

# 📌 Resource Names

| Resource           | Name                   |
| ------------------ | ---------------------- |
| Resource Group     | `rg-azureml-demo`      |
| Azure ML Workspace | `mlw-house-price`      |
| Compute Instance   | `ci-house-price`       |
| Experiment         | `house-price-training` |
| Region             | `eastus`               |
| Compute Size       | `Standard_D2_v3`       |
