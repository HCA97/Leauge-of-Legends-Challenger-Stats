import json
import datetime as dt
import os
import pandas as pd
import requests
from requests.adapters import HTTPAdapter, Retry

from prefect_gcp.cloud_storage import GcsBucket
from prefect import task, flow
from prefect.tasks import task_input_hash

import config as cfg


SESSION = requests.Session()
retries = Retry(total=5,
                backoff_factor=0.5,
                status_forcelist=[ 429 ])
SESSION.mount('https://', 
            HTTPAdapter(max_retries=retries))


@task(log_prints=True)
def get_summoner_ids(summoner_name: str) -> str:
    with SESSION.get(f'{cfg.REQUEST_URLS["SUMMONER-V4"]}/lol/summoner/v4/summoners/by-name/{summoner_name}',
                      headers= {"X-Riot-Token": cfg.RIOT_API_KEY}) as req:
        if req.status_code == 200:
            data = req.json()
            return {
                'puuid': data['puuid'],
                'id': data['id'],
                'name': summoner_name
            }
    return {}

@task(log_prints=True)
def get_player_rank(summoner_id: str, queue: str) -> dict:
    with SESSION.get(f'{cfg.REQUEST_URLS["LEAUGE-V4"]}/lol/league/v4/entries/by-summoner/{summoner_id}',
                    headers= {"X-Riot-Token": cfg.RIOT_API_KEY}) as req:
        if req.status_code == 200:
            data = req.json()
            for d in data:
                if d['queueType'] == queue:
                    return {
                        'tier': d['tier'],
                        'league_points': d['leaguePoints'],
                        'wins': d['wins'],
                        'losses': d['losses'],
                        'win_rate': d['wins'] / (d['losses'] + d['wins'])
                    }
        return {}

@task(log_prints=True)
def save_data(data: pd.DataFrame, path: str, dtypes: dict) -> None:
    data.astype(dtype=dtypes)
    data.to_parquet(path, compression='gzip')

@task(log_prints=True)
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
            

    print(f'In total {len(match_ids)} played this season.')
    return match_ids

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

    return participants

@flow(name='Process-Matches', log_prints=True)
def process_matches(summoner_ids: dict, start_time: dt.datetime):
    match_ids = match_history(summoner_ids['puuid'], start_time)
    participants = []
    for match_id in match_ids[:10]:
        participants.extend(get_match_info(match_id))
    participants = pd.DataFrame(participants)
    save_data(participants, 
              f'players_{summoner_ids["name"]}_{start_time.strftime("%m-%d-%Y")}.parquet', 
              cfg.DTYPE_MATCH
    )

@flow(name='Process-Player', log_prints=True)
def process_player(summoner_ids: dict):   
    player_rank = get_player_rank(summoner_ids['id'], 'RANKED_SOLO_5x5')  
    with open(f'player_rank_{summoner_ids["name"]}.json', 'w') as f:
        json.dump(player_rank, f, indent=4)

@flow(name='Process', log_prints=True)
def process(summoner_name: str, start_time: dt.datetime):
    ids = get_summoner_ids(summoner_name)
    if ids:
        process_player(ids)
        process_matches(ids, start_time)

if __name__ == '__main__':
    summoner_name = 'FREEDOMFIGHTER28'
    start_time = dt.datetime(2023, 1, 11) # when the new season started

    process(summoner_name, start_time)