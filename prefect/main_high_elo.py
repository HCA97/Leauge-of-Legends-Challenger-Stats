import datetime as dt
from typing import Optional
import os

import pandas as pd
import requests
from requests.adapters import HTTPAdapter, Retry

from prefect import flow, task
from prefect_gcp.cloud_storage import GcsBucket
from prefect_gcp import GcpCredentials
from prefect.tasks import task_input_hash
from google.cloud import bigquery

import config as cfg

#
#
#

SESSION = requests.Session()
retries = Retry(total=5,
                backoff_factor=0.5,
                status_forcelist=[ 429 ])
SESSION.mount('https://', 
            HTTPAdapter(max_retries=retries))


#
#
#

def _get_all_ids_by_summoner_id(summoner_id):
    with SESSION.get(f'{cfg.REQUEST_URLS["SUMMONER-V4"]}/lol/summoner/v4/summoners/{summoner_id}',
                      headers= {"X-Riot-Token": cfg.RIOT_API_KEY}) as req:
        if req.status_code == 200:
            return req.json()
    return {}

def _get_all_ids_by_summoner_name(summoner_name):
    with SESSION.get(f'{cfg.REQUEST_URLS["SUMMONER-V4"]}/lol/summoner/v4/summoners/by-name/{summoner_name}',
                      headers= {"X-Riot-Token": cfg.RIOT_API_KEY}) as req:
        if req.status_code == 200:
            return req.json()
    return {}

#
#
#

@task()
def high_elo_players(leauge: str, queue: str) -> list:
    data = []
    with SESSION.get(f'{cfg.REQUEST_URLS["LEAUGE-V4"]}/lol/league/v4/{leauge}/by-queue/{queue}',
                      headers= {"X-Riot-Token": cfg.RIOT_API_KEY}) as req:
        if req.status_code == 200:
            data = req.json()['entries']

    print(f'In total {leauge}-{queue} players exists {len(data)}.')
    return data

@task()
def get_puuid(summoner_name, summoner_id: str) -> str:
    data = _get_all_ids_by_summoner_name(summoner_name)
    if data:
        return data['puuid']

    # if we ask wrong summoner ids multiple times we get IP ban
    print(f'Summoner Name ({summoner_name}) not exists using Summoner ID ({summoner_id}).')
    data = _get_all_ids_by_summoner_id(summoner_id)
    if data:
        return data['puuid']
    
    return ''

@task()
def add_puuid(players: list) -> pd.DataFrame:

    new_players = []

    for i, player in enumerate(players):
        if i % 10 == 0:
            print(f'[ADD PUIID] {i}/{len(players)} are done.')

        summoner_name, summoner_id = player['summonerName'], player['summonerId']
        puuid = get_puuid(summoner_name, summoner_id)

        if puuid:
            player['summonerPuuid'] = puuid
            new_players.append(player)
    
    print(f'[ADD PUIID] In total {len(new_players)}/{len(players)} puiids obtained.')

    return pd.DataFrame(new_players)

@task()
def player_transform(players: pd.DataFrame, leauge: str, queue: str) -> pd.DataFrame:
    players = players.drop(columns=['rank', 'veteran', 'inactive', 'freshBlood', 'hotStreak'])
    players['winRate'] = players['wins'] / (players['wins'] + players['losses'])
    players['totalGames'] = players['wins'] + players['losses']
    players['leauge'] = leauge
    players['queue'] = queue
    return players

@task()
def save_data(data: pd.DataFrame, path: str, dtypes: dict) -> None:
    data.astype(dtype=dtypes)
    data.to_parquet(path, compression='gzip')

def upload_to_bq(data: pd.DataFrame, 
                 table_name: str, 
                 schema: list,
                 partitioning: str = 'DAY', 
                 clustering_fields: list = []) -> None:
    gcp_credentials_block = GcpCredentials.load("de-zoomcamp-sa")
    credentials = gcp_credentials_block.get_credentials_from_service_account()
    
    client = bigquery.Client(project=cfg.PROJECT_ID, credentials=credentials)
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
        schema=schema,
        time_partitioning=bigquery.table.TimePartitioning(type_=partitioning),
        clustering_fields=clustering_fields
    )

    table_id = f'{cfg.TABLE_ID}.{table_name}' 
    job = client.load_table_from_dataframe(data, table_id, job_config=job_config) # Make an API request
    job.result() # Wait for job to finish



@task()
def match_history(summoner_puuid: str, start_time: dt.datetime, count: int = 100, match_type: str = 'ranked') -> list:
    match_ids = []
    start = 0

    while True:
        with SESSION.get(f'{cfg.REQUEST_URLS["MATCH-V5"]}/lol/match/v5/matches/by-puuid/{summoner_puuid}/ids',
                        params={
                            'startTime': int(start_time.timestamp()),
                            'type': match_type,
                            'count': count,
                            'start': start
                        },
                        headers= {"X-Riot-Token": cfg.RIOT_API_KEY}) as req:
            
            data = []
            if req.status_code == 200:
                data = req.json()

            if not data:
                break

            match_ids.extend(data)
            start += count

            if len(data) < count:
                break            

    print(f'In total {len(match_ids)} played this season.')
    return match_ids

@task()
def players_match_history(players, start_time):

    match_histories = []
    for i, summoner_puuid in enumerate(players):

        if i % 10 == 0:
            print(f'{i}/{len(players)} are done.')
        matches = match_history(summoner_puuid, start_time)
        match_histories.extend(matches)

    return list(set(match_histories))

@task(log_prints=True, cache_key_fn=task_input_hash, cache_expiration=dt.timedelta(days=1))
def get_match_info(match_id) -> list:
    with SESSION.get(f'{cfg.REQUEST_URLS["MATCH-V5"]}/lol/match/v5/matches/{match_id}',
                    headers= {"X-Riot-Token": cfg.RIOT_API_KEY}) as req:
        if req.status_code == 200:
            data = req.json()
        else:
            print(f'Failed to do request ({req.status_code})')
            return []
        

    # creation time
    creation_time = dt.datetime.fromtimestamp(data['info']['gameCreation'] / 1000.0)
    game_start_time = dt.datetime.fromtimestamp(data['info']['gameStartTimestamp'] / 1000.0)
    # game length
    duration_min = data['info']['gameDuration'] / 60

    participants = []

    for info in data['info']['participants']:
        summoner_puuid = info['puuid']
        summoner_id = info['summonerId']
        summoner_name = info['summonerName']

        # champion played
        champion = info['championName']

        # K.D.A
        kills = info['kills']
        deaths = info['deaths']
        assits = info['assists']
        kda = info['challenges']['kda']

        # Role (MID/ADC/TOP/JG/SUP)
        lane = info['teamPosition']

        # Damage to Champions
        damage_dealt = info['totalDamageDealtToChampions']
        damage_per_min = info['challenges']['damagePerMinute']
        damage_taken = info['totalDamageTaken']

        # Gold Earn
        gold = info['goldEarned']
        gold_per_min = info['challenges']['goldPerMinute']

        # Outcome
        win = info['win']

        # Creep Slain
        cs = info['totalMinionsKilled'] + info['neutralMinionsKilled']

        # vision score
        vision_score = info['visionScore']
        vision_score_per_min = info['challenges']['visionScorePerMinute']


        # game info
        surrender = info['gameEndedInSurrender']

        participants.append({
            'summoner_puuid': summoner_puuid,
            'summoner_id': summoner_id,
            'summoner_name': summoner_name,
            'match_id': match_id,
            'creation_time': creation_time,
            'game_start_time': game_start_time,
            'duration_min': duration_min,
            'champion': champion,
            'kills': kills,
            'deaths': deaths,
            'assits': assits,
            'kda': kda,
            'lane': lane,
            'damage_dealt': damage_dealt,
            'damage_per_min': damage_per_min,
            'damage_taken': damage_taken,
            'gold': gold,
            'gold_per_min': gold_per_min,
            'win': win,
            'cs': cs,
            'vision_score': vision_score,
            'vision_score_per_min': vision_score_per_min,
            'surrender': surrender
        })


@flow(name="Process-Players", log_prints=True)
def process_players(leauge, queue):
    players = high_elo_players(leauge, queue)
    players = add_puuid(players)
    players = player_transform(players, leauge, queue)
    save_data(players, f'players_{leauge}_{queue}.parquet', cfg.DTYPE_PLAYER)
    return players

@flow()
def process_matches(puuids, start_time):
    # matches
    match_ids = players_match_history(puuids, start_time)

    print(f'Total Challenger games {len(match_ids)}.')
    participants = []
    for i, match_id in enumerate(match_ids):
        if i % 10 == 0:
            print(f'[PROCESS MATCHES] {i}/{len(match_ids)} are done.')
        participants.extend(get_match_info(match_id))
    participants = pd.DataFrame(participants)

    save_data(participants, f'games_{leauge}_{queue}.parquet', cfg.DTYPE_MATCH)

@flow('Process-Data', log_prints=True)
def process_data(leauge: str, queue: str, start_time: Optional[dt.datetime]) -> None:
    '''get the challenger players and teir games.'''

    # get high elo players players
    players = process_players(leauge, queue)
    puuids = list(players['summonerPuuid'])

    # get their matches matches
    if start_time is None:
        start_time = dt.datetime.today() - dt.timedelta(1)
    process_matches(puuids, start_time)





if __name__ == '__main__':
    leauge = 'challengerleagues'
    queue = 'RANKED_SOLO_5x5'

    process_data(leauge, queue)