#! /bin/bash
export HOME=/root
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O $HOME/miniconda.sh
bash $HOME/miniconda.sh -b -p $HOME/miniconda
eval "$($HOME/miniconda/bin/conda shell.bash hook)" 
conda init
conda config --set auto_activate_base true
conda update conda -y
conda install python=3.8 -y
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
export PREFECT_API_KEY="${prefect_key}"
export PREFECT_API_URL="https://api.prefect.cloud/api/accounts/${prefect_account_id}/workspaces/${prefect_workspace_id}"
export PREFECT_PROFILE="default"
prefect agent start -q 'project'