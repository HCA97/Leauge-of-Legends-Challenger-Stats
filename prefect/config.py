import os
import logging

import requests
from requests.adapters import HTTPAdapter, Retry

RIOT_API_KEY = os.getenv('ROIT_API_KEY')
REGION = os.getenv("REGION", 'euw1')

if REGION == 'euw1':
    REQUEST_URLS = {
        "LEAUGE-V4" : 'https://euw1.api.riotgames.com',
        'SUMMONER-V4': 'https://euw1.api.riotgames.com',
        'MATCH-V5': 'https://europe.api.riotgames.com'
    }



logging.basicConfig(
    format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("challenger_players.log"),
        logging.StreamHandler()
    ])

SESSION = requests.Session()
retries = Retry(total=5,
                backoff_factor=0.5,
                status_forcelist=[ 429 ])
SESSION.mount('https://', 
            HTTPAdapter(max_retries=retries))



DTYPE_PLAYER = {
    "winRate": float,
    'wins': int,
    'losses': int,
    'totalGames': int,
    'summonerName': str,
    'summonerPuuid': str,
    'summonerId': str,
    'leauge': str,
    'queue': str
}

DTYPE_MATCH = {
    'summoner_puuid': str,
    'summoner_id': str,
    'summoner_name': str,
    'match_id': str,
    'duration_min': float,
    'champion': str,
    'kills': int,
    'deaths': int,
    'assits': int,
    'kda': float,
    'lane': str,
    'damage_dealt': int,
    'damage_per_min': float,
    'damage_taken': int,
    'gold': int,
    'gold_per_min': float,
    'win': bool,
    'cs': int,
    'vision_score': int,
    'surrender': bool,
    'vision_score_per_min': float
}