{{
    config(
        materialized="table",
        partition_by={
            "field": "game_start_time",
            "data_type": "datetime",
            "granularity": "hour",
        },
    )
}}


select * except (rn, retrieve_time)
from
    (
        select
            m.*,
            row_number() over (
                partition by summoner_puuid, match_id order by retrieve_time desc
            ) as rn
        from {{ source("warehouse", "matches") }} as m
        where m.lane != ''
    )
where rn = 1
