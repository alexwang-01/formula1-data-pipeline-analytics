SELECT season,
       CASE WHEN NOT started THEN 'Non-start (source-derived)'
            WHEN finish_status = 'DSQ' THEN 'Disqualified'
            WHEN finished THEN 'Finished without retirement'
            WHEN retirement_reason IN ('Collision', 'Collision damage', 'Accident', 'Accident damage', 'Spun off') THEN 'Incident-related retirement'
            WHEN retirement_reason IN ('Engine', 'Undertray', 'Brakes', 'Hydraulics', 'Overheating', 'Gearbox', 'Oil leak', 'Suspension', 'Rear wing', 'Turbo', 'Clutch', 'Electrical', 'Chassis', 'Oil pressure', 'Fuel system', 'Throttle', 'Power unit', 'Steering', 'Water leak', 'Fuel pump', 'Transmission') THEN 'Mechanical-labelled retirement'
            ELSE 'Other / unclassified retirement' END AS outcome_group,
       COUNT(*) AS entries
FROM explore.recent GROUP BY ALL ORDER BY season, outcome_group;
