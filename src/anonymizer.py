"""Module de conformité RGPD — masquage des champs personnels sensibles avant
tout passage en couche "processed". POC personnel, données déjà fictives.

Principe de minimisation appliqué aux 3 champs identifiés comme PII non
masqués par le générateur (voir config/data_dictionary.yaml) : nom, téléphone,
IBAN. Email, date de naissance et adresse restent en clair dans ce POC (hors
périmètre de cette itération, signalé comme tel dans le dictionnaire de
données plutôt que masqué à moitié en silence).
"""
import hashlib
from pathlib import Path

import pandas as pd

# Sel de pseudonymisation. En production : secret géré hors code (variable
# d'environnement ou vault), jamais committé — ici en clair car les données
# elles-mêmes sont fictives, ce qui rendrait un vrai secret sans objet.
SEL_PSEUDONYMISATION = "poc-data-quality-pipeline-sel"

DATA_PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"


def pseudonymiser_identite(numero_societaire, sel=SEL_PSEUDONYMISATION):
    """Dérive un pseudonyme stable à partir du numéro de sociétaire (pas du
    nom lui-même, pour ne rien faire fuiter du nom dans le hash) — même
    sociétaire, même pseudonyme à chaque exécution ; non réversible sans le sel."""
    empreinte = hashlib.sha256(f"{sel}:{numero_societaire}".encode()).hexdigest()[:10].upper()
    return f"SOCIETAIRE-{empreinte}"


def masquer_telephone(telephone):
    """Conserve les 2 premiers et 2 derniers chiffres, masque le reste.
    Un numéro trop court (déjà signalé en anomalie par quality_engine) est
    masqué intégralement plutôt que de risquer d'exposer un fragment trop
    court pour être utile mais trop long pour être anonyme."""
    if pd.isna(telephone):
        return telephone
    tel = str(telephone)
    if len(tel) < 6:
        return "*" * len(tel)
    return tel[:2] + "*" * (len(tel) - 4) + tel[-2:]


def masquer_iban(iban):
    """Conserve le code pays + les 4 derniers caractères, masque le reste."""
    if pd.isna(iban):
        return iban
    compact = str(iban).replace(" ", "")
    if len(compact) < 8:
        return "*" * len(compact)
    return compact[:4] + " " + "*" * (len(compact) - 8) + " " + compact[-4:]


def anonymize_societaires(df):
    """Retourne une copie du DataFrame avec nom/prenom/telephone/iban masqués.
    Ne modifie jamais le DataFrame source."""
    df_anon = df.copy()
    df_anon["nom"] = df_anon["numero_societaire"].apply(pseudonymiser_identite)
    df_anon["prenom"] = ""
    df_anon["telephone"] = df_anon["telephone"].apply(masquer_telephone)
    df_anon["iban"] = df_anon["iban"].apply(masquer_iban)
    return df_anon


def main():
    from quality_engine import DATA_RAW, run_quality_suite, lignes_valides

    df = pd.read_csv(DATA_RAW, dtype=str)
    resultats = run_quality_suite(df)
    df_valides = lignes_valides(df, resultats)

    df_anon = anonymize_societaires(df_valides)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "societaires_anonymises.csv"
    df_anon.to_csv(out_path, index=False, encoding="utf-8")
    print(f"{len(df_anon)} lignes valides anonymisées -> {out_path}")
    print(df_anon[["numero_societaire", "nom", "prenom", "telephone", "iban"]].head(3).to_string(index=False))


if __name__ == "__main__":
    main()
