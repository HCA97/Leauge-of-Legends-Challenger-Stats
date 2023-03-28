# de-zoomcamp-project
final project for de-zoomcamp


# Setup

## Leauge of Legends API

Create a leauge of legends account. (https://developer.riotgames.com/)

Use development `DEVELOPMENT API KEY`, it will reset everyday so you need to renew it.

## Cloud

Use terraform to build needed infrastructure. (storage, bigquery, compute engine and a service account)

Setup the compute engine. 

```bash
wget https://repo.anaconda.com/archive/Anaconda3-2023.03-Linux-x86_64.sh
chmod +x Anaconda3-2023.03-Linux-x86_64.sh
./Anaconda3-2023.03-Linux-x86_64.sh # set conda init [yes]
source .bashrc
conda create --name prefect python=3.8
conda activate prefect
pip install \
    requests \
    pandas==1.5.2 \
    prefect==2.7.7 \
    prefect-sqlalchemy==0.2.2 \
    prefect-gcp[cloud_storage]==0.2.4 \
    protobuf==4.21.11 \
    pyarrow==10.0.1 \
    pandas-gbq==0.18.1 \
    google-cloud-storage \
    gcsfs
export RIOT_API_KEY="$RIOT_API_KEY"
export PREFECT_API_KEY="$PREFECT_API_KEY"
export PREFECT_API_URL="https://api.prefect.cloud/api/accounts/$ACCOUNT_ID/workspaces/$WORKSPACE_ID"
export PREFECT_PROFILE="default"
prefect agent start -q 'project'
```

## Prefect

prefect deployment build main_track_player.py:process -n test -q test -sb gcs/test -a

Create a prefect cloud account

Setup workspace.

```bash
git clone https://github.com/HCA97/de-zoomcamp-project.git
cd de-zoomcamp-project/prefect
pip install -r requiremetns.txt
```

Login prefect
```bash
prefect cloud login
```

Create Blocks
```bash
cd prefect
python blocks.py --sa_path="$SA_PATH" --riot_api_key="$RIOT_API_KEY"
```

Setup blocks we need.
```bash
prefect deployment build main_high_elo.py:process -n project -q project -sb gcs/de-project-deployment -a
```
## DBT