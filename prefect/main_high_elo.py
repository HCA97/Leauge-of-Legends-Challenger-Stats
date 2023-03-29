import datetime as dt
from typing import Optional

import pandas as pd

from prefect import flow, task
from prefect.blocks.system import Secret

from prefect.tasks import task_input_hash
from google.cloud import bigquery

import config as cfg
import utils


# 
# REFECT TASKS
#

@task(name='High-Elo-Players', 
      cache_key_fn=task_input_hash, 
      cache_expiration=dt.timedelta(hours=1))
def high_elo_players(leauge: str, queue: str) -> list:
    data = []
    with cfg.SESSION.get(f'{cfg.REQUEST_URLS["LEAUGE-V4"]}/lol/league/v4/{leauge}/by-queue/{queue}',
                      headers= {"X-Riot-Token": Secret.load("riot-api-key").get()}) as req:
        if req.status_code == 200:
            data = req.json()['entries']

    print(f'In total {leauge}-{queue} players exists {len(data)}.')
    return data



@task(name='Add-PUUID', log_prints=True)
def add_puuid(players: list) -> pd.DataFrame:

    new_players = []

    for i, player in enumerate(players):
        if i % 10 == 0:
            print(f'[ADD PUUID] {i}/{len(players)} are done.')

        summoner_name, summoner_id = player['summonerName'], player['summonerId']
        ids = utils.get_summoner_ids(summoner_name, summoner_id)

        if ids:
            player['summonerPuuid'] = ids['puuid']
            player['summonerLevel'] = ids['summonerLevel']
            new_players.append(player)
    
    print(f'[ADD PUUID] In total {len(new_players)}/{len(players)} puiids obtained.')

    return pd.DataFrame(new_players)

@task(name='Player-Transform')
def player_transform(players: pd.DataFrame, leauge: str, queue: str) -> pd.DataFrame:
    players = players.drop(columns=['rank', 'veteran', 'inactive', 'freshBlood', 'hotStreak'])
    players['winRate'] = players['wins'] / (players['wins'] + players['losses'])
    players['totalGames'] = players['wins'] + players['losses']
    players['leauge'] = leauge
    players['queue'] = queue
    players['retriveTime'] = dt.datetime.utcnow()
    return players


@task(name='Upload-To-BQ', log_prints=True)
def upload_to_bq(data: pd.DataFrame, 
                 table_name: str, 
                 partitioning_field: str,
                 partitioning_type: str = 'DAY',
                 clustering_fields: Optional[list] = None) -> None:

    
    client = bigquery.Client(project=cfg.CREDENTIALS.project_id, credentials=cfg.CREDENTIALS)
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
        time_partitioning=bigquery.table.TimePartitioning(
            type_=partitioning_type,
            field=partitioning_field
        ),
        clustering_fields=clustering_fields
    )

    table_id = f'{cfg.TABLE_ID}.{table_name}' 
    job = client.load_table_from_dataframe(data, table_id, job_config=job_config) # Make an API request
    job.result() # Wait for job to finish




@task(name="Match-History", log_prints=True)
def players_match_history(players, start_time):

    match_histories = []
    for i, summoner_puuid in enumerate(players):

        if i % 10 == 0:
            print(f'{i}/{len(players)} are done.')
        matches = utils.match_history(summoner_puuid, start_time)
        match_histories.extend(matches)

    return list(set(match_histories))

@task(name='Match-Infos', log_prints=True)
def match_infos(match_ids):

    participants = []
    
    for i, match_id in enumerate(match_ids):
        if i % 10 == 0:
            print(f'[PROCESS MATCHES] {i}/{len(match_ids)} are done.')
        data = utils.get_match_info(match_id)
        participants.extend(utils.match_transform(data))

    participants = pd.DataFrame(participants)
    participants.astype(cfg.DTYPE_MATCH)
    return participants


#
# PREFECT FLOWS
#

@flow(name="Process-Players", log_prints=True)
def process_players(leauge: str, queue: str) -> list:
    '''collects high elo players and returns their puuids.'''

    # get high elo players
    players = high_elo_players(leauge, queue)

    # get their puuid
    players = add_puuid(players)

    # transform the columns
    players = player_transform(players, leauge, queue)
    players.astype(dtype=cfg.DTYPE_PLAYER)

    # upload to bq
    upload_to_bq(players, 
                 'players', 
                 partitioning_field='retriveTime')
    
    # return puuids for getting match history
    return players['summonerPuuid'].tolist()

@flow(name='Process-Matches', log_prints=True)
def process_matches(puuids: list, start_time: dt.datetime) -> None:
    '''gets match history of given players and start time.'''
    
    # get match ids
    match_ids = players_match_history(puuids, start_time)
    print(f'Total games are {len(match_ids)}.')

    # get match infos
    participants = match_infos(match_ids)

    # upload to bq
    upload_to_bq(participants, 
                'matches', 
                partitioning_field='game_start_time',
                partitioning_type="HOUR",
                clustering_fields=[
                    "lane", "champion" # we will do analysis on lane and champions
                ])

@flow(name='Process-Data', log_prints=True)
def process_data(leauge: str, queue: str, start_time: Optional[dt.datetime]) -> None:
    '''get the high elo players and their games.'''

    # get high elo players players
    puuids = process_players(leauge, queue)

    # get their matches matches
    if start_time is None: 
        # get yesterdays data if start_time is none
        start_time = dt.datetime.utcnow() - dt.timedelta(1)
    process_matches(puuids, start_time)


if __name__ == '__main__':
    leauge = 'challengerleagues'
    queue = 'RANKED_SOLO_5x5'
    start_time = dt.datetime(2023, 3, 28)

    process_data(leauge, queue, start_time)