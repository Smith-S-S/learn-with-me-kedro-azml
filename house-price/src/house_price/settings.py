"""Project settings. There is no need to edit this file unless you want to change values
from the Kedro defaults. For further information, including these default values, see
https://docs.kedro.org/en/0.19.14/kedro_project_setup/settings.html."""

# =============================================================================
# CREDENTIALS PLUMBING -- so a bare `kedro azureml run` just works
# -----------------------------------------------------------------------------
# Kedro imports this module during bootstrap, BOTH on your laptop (before the
# plugin submits the job) and inside the Azure container (before the catalog is
# built). That makes it the one place that can serve both sides.
#
# LOCALLY: read .env, so you never have to `export` anything by hand.
# ON AZURE: .env is deliberately not uploaded (.amlignore) -- but kedro-azureml
#   already ships the key inside its own KEDRO_AZURE_RUNNER_CONFIG blob, so we
#   just unpack it back into AZURE_STORAGE_ACCOUNT_KEY. That is the variable
#   conf/base/credentials.yml interpolates with ${oc.env:...}.
# =============================================================================
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parents[2] / ".env")
except ImportError:
    # Only needed on your laptop. The Azure container has no .env to read (it is
    # blocked in .amlignore), so python-dotenv is deliberately NOT a dependency
    # of the Azure ML environment -- don't fail the job over a missing import.
    pass

if not os.getenv("AZURE_STORAGE_ACCOUNT_KEY"):
    print("~~~~~~~~~~~~~~ not found AZURE_STORAGE_ACCOUNT_KEY~~~~~~~~~~~~~")
    _runner_config = os.getenv("KEDRO_AZURE_RUNNER_CONFIG")
    print("~~~~~~~~~~~~~~ found KEDRO_AZURE_RUNNER_CONFIG~~~~~~~~~~~~~", _runner_config)
    print("===========================>", _runner_config)
    if _runner_config:
        _key = json.loads(_runner_config).get("storage_account_key")
        print("~~~~~~~~~~~~~~ found storage_account_key~~~~~~~~~~~~~", _key)
        print("===========================>", _key)
        if _key:
            os.environ["AZURE_STORAGE_ACCOUNT_KEY"] = _key
            print("~~~~~~~~~~~~~~ found storage_account_key~~~~~~~~~~~~~", os.getenv("AZURE_STORAGE_ACCOUNT_KEY"))
            print("===========================>", os.getenv("AZURE_STORAGE_ACCOUNT_KEY"))

# Instantiated project hooks.
# For example, after creating a hooks.py and defining a ProjectHooks class there, do
# from house_price.hooks import ProjectHooks
# Hooks are executed in a Last-In-First-Out (LIFO) order.
# HOOKS = (ProjectHooks(),)

# Installed plugins for which to disable hook auto-registration.
# DISABLE_HOOKS_FOR_PLUGINS = ("kedro-viz",)

# Class that manages storing KedroSession data.
# from kedro.framework.session.store import BaseSessionStore
# SESSION_STORE_CLASS = BaseSessionStore
# Keyword arguments to pass to the `SESSION_STORE_CLASS` constructor.
# SESSION_STORE_ARGS = {
#     "path": "./sessions"
# }

# Directory that holds configuration.
# CONF_SOURCE = "conf"

# Class that manages how configuration is loaded.
# from kedro.config import OmegaConfigLoader

# CONFIG_LOADER_CLASS = OmegaConfigLoader

# Keyword arguments to pass to the `CONFIG_LOADER_CLASS` constructor.
CONFIG_LOADER_ARGS = {
    "base_env": "base",
    "default_run_env": "local",
    # "config_patterns": {
    #     "spark" : ["spark*/"],
    #     "parameters": ["parameters*", "parameters*/**", "**/parameters*"],
    # }
}

# Class that manages Kedro's library components.
# from kedro.framework.context import KedroContext
# CONTEXT_CLASS = KedroContext

# Class that manages the Data Catalog.
# from kedro.io import DataCatalog
# DATA_CATALOG_CLASS = DataCatalog
print("===========> dont have compute cluster, change to compute instance <===============")
# =============================================================================
# WORKAROUND: let `kedro azureml run` target a COMPUTE INSTANCE
# -----------------------------------------------------------------------------
# kedro-azureml assumes the compute is an AmlCompute CLUSTER and reads
# .min_instances / .max_instances off it -- but ONLY to print a log message
# (kedro_azureml/client.py lines 54-57). A ComputeInstance has neither, so the
# run dies with:
#     AttributeError: 'ComputeInstance' object has no attribute 'min_instances'
#
# A compute instance really is exactly one node, so reporting 1 and 1 is honest.
# Kedro imports this settings module during bootstrap, which happens before the
# plugin submits anything -- so the patch is in place by the time it's needed.
# =============================================================================
try:
    from azure.ai.ml.entities import ComputeInstance

    if not hasattr(ComputeInstance, "min_instances"):
        ComputeInstance.min_instances = property(lambda self: 1)
        ComputeInstance.max_instances = property(lambda self: 1)
except ImportError:
    pass  # azure-ai-ml not installed locally; nothing to patch