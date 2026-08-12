-- Mart : dimension sociétaires, une ligne par sociétaire actif dans le
-- référentiel validé/anonymisé.
SELECT
    numero_societaire,
    nom,
    ville,
    code_postal,
    formule,
    statut,
    date_adhesion
FROM stg_societaires
