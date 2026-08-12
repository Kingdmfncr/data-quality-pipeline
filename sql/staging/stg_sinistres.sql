-- Staging : sinistres bruts, typage propre uniquement. La donnée n'est pas
-- filtrée ici : l'intégrité référentielle et la cohérence métier sont
-- évaluées en aval, dans le mart fact_claims, pour rester visibles à l'audit.
SELECT
    sinistre_id,
    numero_societaire,
    CAST(date_sinistre AS DATE) AS date_sinistre,
    type_sinistre,
    CAST(montant_declare AS DOUBLE) AS montant_declare,
    CAST(montant_rembourse AS DOUBLE) AS montant_rembourse,
    statut_sinistre
FROM raw_sinistres
