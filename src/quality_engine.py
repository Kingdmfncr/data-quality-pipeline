"""Moteur de règles qualité déclaratif — POC personnel.
Lit config/rules.yaml (pas de règle codée en dur) et calcule un Data Health
Score à 3 axes (Complétude / Exactitude / Fraîcheur), inspiré de Great
Expectations et des tests dbt. Chaque règle peut être ajoutée ou modifiée
sans toucher au code, seulement au YAML — c'est le point qui distingue ce
moteur d'un script de contrôle qualité ad hoc.
"""
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DATA_RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "societaires_bruts.csv"
DATA_PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"


@dataclass
class Resultat:
    champ: str
    regle: str
    description: str
    categorie: str
    critique: bool
    nb_lignes: int
    nb_violations: int
    taux_conformite_pct: float
    exemples: list = field(default_factory=list)

    @property
    def statut(self):
        if self.nb_violations == 0:
            return "OK"
        return "CRITIQUE" if self.critique else "ALERTE"


# ── Registre des fonctions de règle : chaque fonction retourne un masque booléen
# (True = ligne en violation), à partir du DataFrame et des paramètres YAML. ──

def _regle_not_null(df, champ, **_):
    return df[champ].isna()


def _regle_unique(df, champ, **_):
    return df[champ].duplicated(keep=False) & df[champ].notna()


def _regle_format_email(df, champ, **_):
    return df[champ].notna() & ~df[champ].str.contains("@", na=False)


def _regle_longueur_exacte(df, champ, longueur, **_):
    return df[champ].notna() & (df[champ].astype(str).str.len() != longueur)


def _regle_pas_dans_le_futur(df, champ, **_):
    date_ref = pd.Timestamp(_reference()["date_reference"])
    return df[champ].notna() & (pd.to_datetime(df[champ], errors="coerce") > date_ref)


def _regle_pas_trop_ancienne(df, champ, **_):
    date_ref = pd.Timestamp(_reference()["date_reference"])
    fenetre = _reference()["fenetre_fraicheur_jours"]
    borne = date_ref - pd.Timedelta(days=fenetre)
    return df[champ].notna() & (pd.to_datetime(df[champ], errors="coerce") < borne)


def _regle_age_plausible(df, champ, age_min, age_max, **_):
    date_ref = pd.Timestamp(_reference()["date_reference"])
    ages = (date_ref - pd.to_datetime(df[champ], errors="coerce")).dt.days / 365.25
    return df[champ].notna() & ((ages < age_min) | (ages > age_max))


def _regle_valeur_dans_liste(df, champ, valeurs, **_):
    return df[champ].notna() & ~df[champ].isin(valeurs)


REGISTRE_REGLES = {
    "not_null": _regle_not_null,
    "unique": _regle_unique,
    "format_email": _regle_format_email,
    "longueur_exacte": _regle_longueur_exacte,
    "pas_dans_le_futur": _regle_pas_dans_le_futur,
    "pas_trop_ancienne": _regle_pas_trop_ancienne,
    "age_plausible": _regle_age_plausible,
    "valeur_dans_liste": _regle_valeur_dans_liste,
}

_config_cache = None


def _load_config():
    global _config_cache
    if _config_cache is None:
        with open(CONFIG_DIR / "rules.yaml", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def _reference():
    return _load_config()["reference"]


def run_quality_suite(df):
    config = _load_config()
    resultats = []
    for regle_def in config["regles"]:
        fonction = REGISTRE_REGLES[regle_def["regle"]]
        params = regle_def.get("params", {})
        mask_violations = fonction(df, regle_def["champ"], **params)

        nb = len(df)
        nb_viol = int(mask_violations.sum())
        taux = round(100 * (1 - nb_viol / nb), 2) if nb else 100.0
        exemples = [str(v) for v in df.loc[mask_violations, regle_def["champ"]].head(3).tolist()]

        resultats.append(Resultat(
            champ=regle_def["champ"], regle=regle_def["regle"], description=regle_def["description"],
            categorie=regle_def["categorie"], critique=regle_def.get("critique", False),
            nb_lignes=nb, nb_violations=nb_viol, taux_conformite_pct=taux, exemples=exemples,
        ))
    return resultats


def resultats_to_dataframe(resultats):
    return pd.DataFrame([{
        "Catégorie": r.categorie, "Champ": r.champ, "Règle": r.regle, "Description": r.description,
        "Statut": r.statut, "Lignes contrôlées": r.nb_lignes, "Violations": r.nb_violations,
        "Conformité (%)": r.taux_conformite_pct,
        "Exemples": ", ".join(str(v) for v in r.exemples) if r.exemples else "-",
    } for r in resultats])


def _score_pondere(resultats):
    if not resultats:
        return 100.0
    poids = [3 if r.critique else 1 for r in resultats]
    scores = [r.taux_conformite_pct for r in resultats]
    return round(sum(w * s for w, s in zip(poids, scores)) / sum(poids), 1)


def data_health_scorecard(resultats):
    """{"Complétude": x, "Exactitude": y, "Fraîcheur": z} — score pondéré par
    catégorie (une règle critique pèse 3x plus qu'une règle non critique)."""
    categories = ["Complétude", "Exactitude", "Fraîcheur"]
    return {cat: _score_pondere([r for r in resultats if r.categorie == cat]) for cat in categories}


def lignes_valides(df, resultats):
    """Lignes sans aucune violation critique — exploitables pour l'étape
    suivante du pipeline (entrepôt). On exclut, on ne corrige jamais à la
    devinette."""
    config = _load_config()
    mask_valide = pd.Series(True, index=df.index)
    for regle_def in config["regles"]:
        if not regle_def.get("critique", False):
            continue
        fonction = REGISTRE_REGLES[regle_def["regle"]]
        params = regle_def.get("params", {})
        mask_violations = fonction(df, regle_def["champ"], **params)
        mask_valide &= ~mask_violations
    return df[mask_valide].copy()


def main():
    df = pd.read_csv(DATA_RAW, dtype=str)
    resultats = run_quality_suite(df)

    print("Data Health Scorecard")
    for categorie, score in data_health_scorecard(resultats).items():
        print(f"  {categorie:12s} : {score}/100")

    df_resultats = resultats_to_dataframe(resultats)
    df_valides = lignes_valides(df, resultats)
    print(f"\nLignes valides (sans violation critique) : {len(df_valides)}/{len(df)}")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    df_resultats.to_csv(DATA_PROCESSED / "quality_report.csv", index=False, encoding="utf-8")
    print(f"Rapport détaillé -> {DATA_PROCESSED / 'quality_report.csv'}")


if __name__ == "__main__":
    main()
