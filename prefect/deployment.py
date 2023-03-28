from prefect.deployments import Deployment
from main_high_elo import process_data
from prefect.filesystems import GCS

gcs_block = GCS.load("de-project-deployment")

gcs_deployment = Deployment.build_from_flow(
    flow=process_data,
    name='process',
    storage=gcs_block,
    parameters={
        '': '',
        '': ''
    }
)

if __name__ == "__main__":
    gcs_deployment.apply()