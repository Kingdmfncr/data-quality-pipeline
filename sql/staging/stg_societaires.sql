-- Staging : sociétaires déjà validés (quality_engine) et anonymisés
-- (anonymizer) en amont. Aucune logique de qualité ici, seulement un
-- typage propre.
SELECT
    numero_societaire,
    nom,
    ville,
    code_postal,
    formule,
    statut,
    CAST(date_adhesion AS DATE) AS date_adhesion
FROM raw_societaires_anonymises
