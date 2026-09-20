-- One pinned snapshot; preserve raw fields not currently exposed by Silver.
CREATE VIEW explore.races AS
SELECT p.*, NULLIF(x.qualificationPositionNumber, '')::INTEGER AS qualifying_position,
       NULLIF(x.pitStops, '')::INTEGER AS pit_stops,
       NULLIF(x.gapMillis, '')::BIGINT AS gap_ms,
       NULLIF(r.circuitLayoutId, '') AS circuit_layout_id,
       p.retirement_reason IS NULL AND p.finish_position IS NOT NULL
         AND p.finish_status NOT IN ('DNS', 'DNQ', 'DSQ', 'EX', 'DQ', 'DNPQ') AS finished,
       p.finish_status NOT IN ('DNS', 'DNQ', 'DNPQ', 'WD')
         AND COALESCE(p.retirement_reason, '') NOT ILIKE '%formation lap%' AS started
FROM analytics.v_race_performance p
JOIN raw.race_results x ON p.race_id = CAST(x.raceId AS BIGINT)
    AND p.driver_id = x.driverId AND p.car_number = x.driverNumber
JOIN raw.races r ON p.race_id = CAST(r.id AS BIGINT)
WHERE p.session_type = 'RACE';

CREATE VIEW explore.recent AS
SELECT * FROM explore.races WHERE season BETWEEN 2023 AND 2025;
