import os

RIOT_API_KEY = os.getenv('ROIT_API_KEY')
REGION = os.getenv("REGION", 'euw1')

if REGION == 'euw1':
    REQUEST_URLS = {
        "LEAUGE-V4" : 'https://euw1.api.riotgames.com',
        'SUMMONER-V4': 'https://euw1.api.riotgames.com',
        'MATCH-V5': 'https://europe.api.riotgames.com'
    }

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