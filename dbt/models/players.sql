{{ config(materialized="table") }}

with
    players as (
        select *
        from {{ source("warehouse", "players") }}
        where
            retrivetime
            = (select max(retrivetime) from {{ source("warehouse", "players") }})
    ),
    lanes as (
        select puuid, lane
        from
            (
                select
                    l.*,
                    row_number() over (
                        partition by puuid order by games_played desc
                    ) as rn
                from
                    (
                        select
                            p.summonerpuuid as puuid, m.lane, count(*) as games_played
                        from players as p
                        join
                            {{ ref("matches") }} as m
                            on p.summonerpuuid = m.summoner_puuid
                        group by p.summonerpuuid, m.lane
                    ) as l
            )
        where rn = 1
    ),
    champions as (
        select puuid, champion, games_played
        from
            (
                select
                    c.*,
                    row_number() over (
                        partition by puuid order by games_played desc
                    ) as rn
                from
                    (
                        select
                            p.summonerpuuid as puuid,
                            m.champion,
                            count(*) as games_played
                        from players as p
                        join
                            {{ ref("matches") }} as m
                            on p.summonerpuuid = m.summoner_puuid
                        group by p.summonerpuuid, m.champion
                    ) as c
            )
        where rn = 1
    )

select
    p.summonerpuuid as puuid,
    p.summonername,
    l.lane,
    p.leaguepoints as lp,
    p.wins,
    p.losses,
    p.winrate as win_rate,
    c.champion,
    c.games_played as games_played_with_champion
from players as p
join lanes as l on l.puuid = p.summonerpuuid
join champions as c on c.puuid = p.summonerpuuid
