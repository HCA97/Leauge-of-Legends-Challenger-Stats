import json
import argparse

from prefect_gcp import GcpCredentials
from prefect.filesystems import GCS
from prefect.blocks.system import Secret

parser = argparse.ArgumentParser('Build Blocks for Prefect')
parser.add_argument('--sa_path')
parser.add_argument('--riot_api_key')
args = parser.parse_args()

with open(args.sa_path) as f:
    sa = json.load(f)


# SERVICE ACCOUNT BLOCK
credentials_block = GcpCredentials(
    service_account_info=sa
)
credentials_block.save("de-project-sa", overwrite=True)

# DEPLOYMENT BLOCK
bucket_storage = GCS(
    service_account_info=json.dumps(sa),
    bucket_path='de-zoomcamp-project-prefect-code-1234'
)
bucket_storage.save("de-project-deployment", overwrite=True)

# RIOT API SECRET
secret_block = Secret(value=args.riot_api_key)
secret_block.save('riot-api-key', overwrite=True)