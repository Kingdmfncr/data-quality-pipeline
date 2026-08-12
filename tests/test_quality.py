"""Tests unitaires — moteur de qualité, anonymisation et pipeline.
Utilise de petits DataFrames construits à la main (pas le générateur complet)
pour que chaque test soit rapide, déterministe et isole une seule règle.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import anonymizer
import generator
import pipeline as data_pipeline
import quality_engine


# ── quality_engine : fonctions de règle individuelles ───────────────────────

def test_not_null_detecte_les_valeurs_manquantes():
    df = pd.DataFrame({"email": ["a@x.fr", None, "b@x.fr"]})
    mask = quality_engine._regle_not_null(df, "email")
    assert mask.tolist() == [False, True, False]


def test_unique_marque_les_deux_cotes_du_doublon():
    df = pd.DataFrame({"numero_societaire": ["SOC-1", "SOC-2", "SOC-1"]})
    mask = quality_engine._regle_unique(df, "numero_societaire")
    assert mask.tolist() == [True, False, True]


def test_format_email_accepte_arobase_refuse_le_reste():
    df = pd.DataFrame({"email": ["bon@exemple.fr", "invalidexemple.fr", None]})
    mask = quality_engine._regle_format_email(df, "email")
    # ligne 0 valide, ligne 1 en violation, ligne 2 (null) hors périmètre de cette règle
    assert mask.tolist() == [False, True, False]


def test_longueur_exacte():
    df = pd.DataFrame({"telephone": ["0612345678", "06123"]})
    mask = quality_engine._regle_longueur_exacte(df, "telephone", longueur=10)
    assert mask.tolist() == [False, True]


def test_age_plausible_rejette_futur_et_centenaire():
    quality_engine._config_cache = None  # force le rechargement de rules.yaml
    df = pd.DataFrame({"date_naissance": ["1990-01-01", "1899-06-12", "2030-01-01"]})
    mask = quality_engine._regle_age_plausible(df, "date_naissance", age_min=18, age_max=110)
    assert mask.tolist() == [False, True, True]


def test_valeur_dans_liste():
    df = pd.DataFrame({"statut": ["Actif", "Inconnu", None]})
    mask = quality_engine._regle_valeur_dans_liste(df, "statut", valeurs=["Actif", "Résilié"])
    assert mask.tolist() == [False, True, False]


# ── quality_engine : Data Health Score et sélection des lignes valides ─────

def test_data_health_scorecard_penalise_plus_les_regles_critiques():
    quality_engine._config_cache = None
    df = generator.generate_societaires(n=200)
    resultats = quality_engine.run_quality_suite(df)
    scorecard = quality_engine.data_health_scorecard(resultats)
    assert set(scorecard) == {"Complétude", "Exactitude", "Fraîcheur"}
    assert all(0 <= score <= 100 for score in scorecard.values())


def test_lignes_valides_exclut_les_violations_critiques():
    quality_engine._config_cache = None
    df = generator.generate_societaires(n=200)
    resultats = quality_engine.run_quality_suite(df)
    df_valides = quality_engine.lignes_valides(df, resultats)
    assert len(df_valides) < len(df)  # le jeu généré contient des anomalies critiques
    assert len(df_valides) > 0


def test_generate_societaires_reproductible_avec_le_meme_seed():
    df1 = generator.generate_societaires(n=100)
    df2 = generator.generate_societaires(n=100)
    pd.testing.assert_frame_equal(df1, df2)


# ── anonymizer : pseudonymisation et masquage ───────────────────────────────

def test_pseudonymiser_identite_est_stable_et_ne_contient_pas_le_numero_en_clair():
    p1 = anonymizer.pseudonymiser_identite("SOC-100042")
    p2 = anonymizer.pseudonymiser_identite("SOC-100042")
    assert p1 == p2
    assert "100042" not in p1


def test_pseudonymiser_identite_differe_selon_le_sociétaire():
    assert anonymizer.pseudonymiser_identite("SOC-1") != anonymizer.pseudonymiser_identite("SOC-2")


def test_masquer_telephone_conserve_la_longueur_et_masque_le_milieu():
    masque = anonymizer.masquer_telephone("0612345678")
    assert len(masque) == 10
    assert masque[:2] == "06"
    assert masque[-2:] == "78"
    assert "1234567" not in masque


def test_masquer_iban_conserve_pays_et_4_derniers_caracteres():
    masque = anonymizer.masquer_iban("FR7630006000011234567890189")
    assert masque.startswith("FR76")
    assert masque.endswith("0189")


def test_anonymize_societaires_ne_laisse_plus_aucun_nom_en_clair():
    df = generator.generate_societaires(n=50)
    df_anon = anonymizer.anonymize_societaires(df)
    noms_originaux = set(df["nom"])
    assert not set(df_anon["nom"]).intersection(noms_originaux)
    assert (df_anon["prenom"] == "").all()
    assert len(df_anon) == len(df)  # l'anonymisation ne doit jamais faire perdre de lignes


# ── pipeline : intégrité référentielle du mart fact_claims ─────────────────

def test_fact_claims_detecte_les_references_orphelines():
    dim = pd.DataFrame({
        "numero_societaire": ["SOC-1"], "nom": ["X"], "ville": ["Rouen"],
        "code_postal": ["76000"], "formule": ["Confort"], "statut": ["Actif"],
        "date_adhesion": ["2020-01-01"],
    })
    sinistres = pd.DataFrame({
        "sinistre_id": ["SIN-1", "SIN-2"],
        "numero_societaire": ["SOC-1", "SOC-999"],  # SOC-999 n'existe pas dans dim
        "date_sinistre": ["2021-01-01", "2021-01-01"],
        "type_sinistre": ["Vol", "Vol"],
        "montant_declare": [100.0, 100.0],
        "montant_rembourse": [50.0, 0.0],
        "statut_sinistre": ["Remboursé", "Déclaré"],
    })
    tables, log, con = data_pipeline.run_pipeline(dim, sinistres)
    con.close()

    assert (log["statut"] == "Succès").all()
    fact = tables["fact_claims"]
    assert fact.loc[fact["sinistre_id"] == "SIN-1", "societaire_existe"].iloc[0] == True
    assert fact.loc[fact["sinistre_id"] == "SIN-2", "societaire_existe"].iloc[0] == False


def test_fact_claims_detecte_un_remboursement_incoherent():
    dim = pd.DataFrame({
        "numero_societaire": ["SOC-1"], "nom": ["X"], "ville": ["Rouen"],
        "code_postal": ["76000"], "formule": ["Confort"], "statut": ["Actif"],
        "date_adhesion": ["2020-01-01"],
    })
    sinistres = pd.DataFrame({
        "sinistre_id": ["SIN-1"], "numero_societaire": ["SOC-1"],
        "date_sinistre": ["2021-01-01"], "type_sinistre": ["Vol"],
        "montant_declare": [100.0], "montant_rembourse": [150.0],  # > montant déclaré
        "statut_sinistre": ["Remboursé"],
    })
    tables, log, con = data_pipeline.run_pipeline(dim, sinistres)
    con.close()
    assert tables["fact_claims"]["remboursement_incoherent"].iloc[0] == True


def test_fact_claims_detecte_un_sinistre_avant_adhesion():
    dim = pd.DataFrame({
        "numero_societaire": ["SOC-1"], "nom": ["X"], "ville": ["Rouen"],
        "code_postal": ["76000"], "formule": ["Confort"], "statut": ["Actif"],
        "date_adhesion": ["2022-06-01"],
    })
    sinistres = pd.DataFrame({
        "sinistre_id": ["SIN-1"], "numero_societaire": ["SOC-1"],
        "date_sinistre": ["2021-01-01"],  # avant l'adhésion
        "type_sinistre": ["Vol"], "montant_declare": [100.0],
        "montant_rembourse": [0.0], "statut_sinistre": ["Déclaré"],
    })
    tables, log, con = data_pipeline.run_pipeline(dim, sinistres)
    con.close()
    assert tables["fact_claims"]["sinistre_avant_adhesion"].iloc[0] == True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
