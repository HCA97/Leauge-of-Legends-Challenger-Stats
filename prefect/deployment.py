from prefect.deployments import Deployment
from main_high_elo import process_data
from prefect.filesystems import GCS
from prefect.server.schemas.schedules import CronSchedule

gcs_block = GCS.load("de-project-deployment")

gcs_deployment = Deployment.build_from_flow(
    flow=process_data,
    name='process',
    work_queue_name="project",
    storage=gcs_block,
    parameters={
        'leauge': 'challengerleagues',
        'queue': 'RANKED_SOLO_5x5'
    },
    schedule=(CronSchedule(cron="0 0 * * *", timezone="UTC"))
)

if __name__ == "__main__":
    gcs_deployment.apply()