{{ config(materialized="table") }}


with
    game_statistics as (
        select
            m.game_start_hour,
            m.lane,
            avg(m.kills) as avg_kills,
            avg(m.deaths) as avg_deaths,
            avg(m.assits) as avg_assists,
            avg(m.duration_min) as avg_game_length,
            avg(m.cs / m.duration_min) as avg_cs_min,
            avg(m.gold / m.duration_min) as avg_gold_min,
            avg(m.damage_dealt / m.duration_min) as avg_dmg_min
        from
            (
                select *, extract(hour from game_start_time) as game_start_hour
                from {{ ref("matches") }}
            ) as m
        group by m.game_start_hour, lane
        order by m.game_start_hour, lane

    ),
    game_distribution as (
        select m.game_start_hour, count(*) as games_played
        from
            (
                select
                    match_id, extract(hour from max(game_start_time)) as game_start_hour
                from {{ ref("matches") }}
                group by match_id
            ) as m
        group by m.game_start_hour
        order by m.game_start_hour
    )

select s.*, d.games_played
from game_statistics as s
join game_distribution as d on s.game_start_hour = d.game_start_hour
