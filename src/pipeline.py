"""Exécuteur SQL en couches, façon dbt, sans dépendance dbt ni entrepôt cloud
à connecter — même logique que le pipeline du projet Unified Customer
Analytics. Charge les CSV déjà validés/anonymisés (étape 2) dans DuckDB,
exécute staging → marts dans un ordre explicite, et persiste le résultat
dans un fichier .duckdb réutilisable par le dashboard (étape 4).
"""
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_RAW = ROOT / "data" / "raw"
ENTREPOT_PATH = DATA_PROCESSED / "entrepot.duckdb"

# Ordre d'exécution explicite : les marts dépendent des deux modèles staging,
# un tri alphabétique du dossier ne suffirait pas à garantir cet ordre.
MODELES = [
    ("staging", "stg_societaires"),
    ("staging", "stg_sinistres"),
    ("marts", "dim_societaires"),
    ("marts", "fact_claims"),
]


def run_pipeline(societaires_anonymises, sinistres, con=None):
    """Retourne (tables: dict[str, DataFrame], execution_log: DataFrame)."""
    con = con or duckdb.connect(database=":memory:")
    con.register("raw_societaires_anonymises", societaires_anonymises)
    con.register("raw_sinistres", sinistres)

    tables = {}
    execution_log = []

    for stage, model_name in MODELES:
        sql = (SQL_DIR / stage / f"{model_name}.sql").read_text(encoding="utf-8")
        try:
            con.execute(f"CREATE OR REPLACE TABLE {model_name} AS {sql}")
            df = con.execute(f"SELECT * FROM {model_name}").fetchdf()
            tables[model_name] = df
            execution_log.append({
                "etape": stage, "modele": model_name, "statut": "Succès",
                "lignes": len(df), "message": "",
            })
        except Exception as exc:  # une erreur sur un modèle ne doit pas arrêter les autres
            execution_log.append({
                "etape": stage, "modele": model_name, "statut": "Échec",
                "lignes": 0, "message": str(exc),
            })

    return tables, pd.DataFrame(execution_log), con


def main():
    societaires_anonymises = pd.read_csv(DATA_PROCESSED / "societaires_anonymises.csv", dtype=str)
    sinistres = pd.read_csv(DATA_RAW / "sinistres_bruts.csv", dtype=str)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    if ENTREPOT_PATH.exists():
        ENTREPOT_PATH.unlink()  # entrepôt reconstruit à chaque exécution, pas d'accumulation

    con = duckdb.connect(database=str(ENTREPOT_PATH))
    tables, log, con = run_pipeline(societaires_anonymises, sinistres, con=con)
    con.close()

    print(log.to_string(index=False))

    fact_claims = tables.get("fact_claims")
    if fact_claims is not None:
        orphelins = fact_claims["societaire_existe"].eq(False).sum()
        avant_adhesion = fact_claims["sinistre_avant_adhesion"].eq(True).sum()
        incoherents = fact_claims["remboursement_incoherent"].eq(True).sum()
        print(f"\nfact_claims : {len(fact_claims)} sinistres")
        print(f"  Sociétaire inexistant  : {orphelins}")
        print(f"  Sinistre avant adhésion : {avant_adhesion}")
        print(f"  Remboursement incohérent : {incoherents}")

    print(f"\nEntrepôt persisté -> {ENTREPOT_PATH}")


if __name__ == "__main__":
    main()
