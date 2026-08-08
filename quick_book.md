az group create --name rg-azureml-demo --location centralindia

az ml workspace create --name mlw-house-price --resource-group rg-azureml-demo

az configure --default group=rg-azureml-demo workspace=mlw-house-price

az ml workspace show -o table

az ml workspace quota show --location centralindia --output table

az ml workspace show --name mlw-house-price --resource-group rg-azureml-demo -o table



az ml compute create \
  --name ci-house-price \
  --type ComputeInstance \
  --size Standard_D2_v3 \
  --workspace-name mlw-house-price \
  --resource-group rg-azureml-demo



az ml workspace delete \
  --name mlw-house-price \
  --resource-group rg-azureml-demo \
  --permanently-delete \
  --yes
az group delete --name rg-azureml-demo --yes --no-wait









export PS1='(\$(basename "$CONDA_DEFAULT_ENV")) \u@\h:\W\$ '