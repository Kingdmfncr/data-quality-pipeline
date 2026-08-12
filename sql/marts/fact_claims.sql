-- Mart : table de faits des sinistres. Tous les sinistres restent visibles
-- ici, même ceux en écart (même principe que fact_orders dans le projet
-- Unified Customer Analytics) : les écarts sont signalés par des colonnes
-- booléennes plutôt qu'exclus en silence. Le filtrage n'a lieu qu'au moment
-- du calcul d'un KPI métier (dashboard), jamais dans le mart lui-même.
SELECT
    s.sinistre_id,
    s.numero_societaire,
    d.numero_societaire IS NOT NULL AS societaire_existe,
    s.date_sinistre,
    (d.date_adhesion IS NOT NULL AND s.date_sinistre < d.date_adhesion) AS sinistre_avant_adhesion,
    s.type_sinistre,
    s.montant_declare,
    s.montant_rembourse,
    (s.montant_rembourse > s.montant_declare) AS remboursement_incoherent,
    s.statut_sinistre
FROM stg_sinistres s
LEFT JOIN stg_societaires d ON s.numero_societaire = d.numero_societaire
