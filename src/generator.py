"""Générateur de données de sociétaires assurance/mutuelle fictives — POC personnel.
Simule un export brut de contrats, avec anomalies insérées volontairement pour
être détectées ensuite par le moteur de qualité (quality_engine.py).
Aucune donnée réelle, aucun assureur/mutuelle réel, aucune personne réelle.
"""
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 42
N_SOCIETAIRES = 1000
N_SINISTRES = 600
ANOMALY_RATE = 0.08

TYPES_SINISTRE = [
    "Dégât des eaux", "Bris de glace", "Vol", "Incendie",
    "Responsabilité civile", "Hospitalisation",
]
STATUTS_SINISTRE = ["Déclaré", "En cours d'instruction", "Remboursé", "Refusé"]

PRENOMS = [
    "Marie", "Jean", "Camille", "Nadia", "Lucas", "Fatou", "Thomas", "Aïcha",
    "Julien", "Chloé", "Kevin", "Amandine", "Karim", "Sophie", "Antoine",
    "Léa", "Moussa", "Emma", "Nicolas", "Sarah", "David", "Manon", "Yanis",
    "Clara", "Mathieu", "Inès", "Romain", "Jade", "Adama", "Laura",
]
NOMS = [
    "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Petit", "Durand",
    "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel", "Garcia",
    "David", "Bertrand", "Roux", "Vincent", "Fontaine", "Chevalier", "Diallo",
    "N'Diaye", "Traoré", "Kouassi", "Nguyen", "Rousseau", "Fournier",
]
VILLES = [
    ("Rouen", "76000"), ("Le Havre", "76600"), ("Dieppe", "76200"),
    ("Évreux", "27000"), ("Caen", "14000"), ("Lille", "59000"),
    ("Paris", "75011"), ("Lyon", "69003"), ("Marseille", "13008"),
    ("Nantes", "44000"), ("Toulouse", "31000"), ("Strasbourg", "67000"),
]
FORMULES = ["Essentielle", "Confort", "Premium"]
STATUTS = ["Actif", "Résilié", "Suspendu"]


def _rng():
    return random.Random(SEED)


def _email_valide(prenom, nom, idx):
    base = f"{prenom.lower()}.{nom.lower().replace(chr(39), '')}{idx}"
    return f"{base}@exemple.fr"


def _iban_fictif(rng, idx):
    # Format FR fictif, jamais un vrai compte : chiffres dérivés de l'index + tirage.
    chiffres = "".join(str(rng.randint(0, 9)) for _ in range(10))
    return f"FR76 3000{idx % 10}0000{idx:05d}{chiffres[:4]}"


def _telephone(rng):
    return "0" + str(rng.randint(6, 7)) + "".join(str(rng.randint(0, 9)) for _ in range(8))


def generate_societaires(n=N_SOCIETAIRES, anomaly_rate=ANOMALY_RATE):
    rng = _rng()
    rows = []
    for i in range(n):
        prenom = rng.choice(PRENOMS)
        nom = rng.choice(NOMS)
        ville, cp = rng.choice(VILLES)
        naissance = date(1941, 1, 1) + timedelta(days=rng.randint(0, 24500))  # ~18 à 85 ans au 2026-08-12
        adhesion = date(2015, 1, 1) + timedelta(days=rng.randint(0, 4000))

        rows.append({
            "numero_societaire": f"SOC-{100000 + i}",
            "civilite": rng.choice(["M.", "Mme"]),
            "nom": nom,
            "prenom": prenom,
            "date_naissance": naissance.isoformat(),
            "email": _email_valide(prenom, nom, i),
            "telephone": _telephone(rng),
            "adresse": f"{rng.randint(1, 150)} rue {rng.choice(NOMS)}",
            "code_postal": cp,
            "ville": ville,
            "iban": _iban_fictif(rng, i),
            "date_adhesion": adhesion.isoformat(),
            "formule": rng.choice(FORMULES),
            "statut": rng.choice(STATUTS),
        })

    df = pd.DataFrame(rows)

    # Anomalies injectées volontairement, réparties en 4 familles cycliques
    # (contrôlé et reproductible, pas un effet de bord du tirage aléatoire).
    n_anom = int(n * anomaly_rate)
    idx_anom = df.sample(n=n_anom, random_state=SEED).index
    for j, i in enumerate(idx_anom):
        kind = j % 4
        if kind == 0:
            # Email invalide (arobase manquante, saisie manuelle défaillante)
            df.loc[i, "email"] = df.loc[i, "email"].replace("@", "")
        elif kind == 1:
            # Date de naissance incohérente (future ou sociétaire centenaire improbable)
            if j % 2 == 0:
                df.loc[i, "date_naissance"] = (date(2026, 1, 1) + timedelta(days=rng.randint(1, 300))).isoformat()
            else:
                df.loc[i, "date_naissance"] = date(1899, 6, 12).isoformat()
        elif kind == 2:
            # Doublon de numéro de sociétaire (deux dossiers, un seul numéro)
            autre = idx_anom[(j + 5) % len(idx_anom)]
            df.loc[i, "numero_societaire"] = df.loc[autre, "numero_societaire"]
        elif kind == 3:
            # Téléphone mal saisi (longueur incorrecte)
            df.loc[i, "telephone"] = df.loc[i, "telephone"][:6]

    # Champs PII (nom, téléphone, IBAN) volontairement laissés en clair à ce stade :
    # c'est le rôle de anonymizer.py, à l'étape suivante, de les masquer avant
    # tout passage en couche "processed".
    return df


def generate_sinistres(societaires_df, n=N_SINISTRES, anomaly_rate=ANOMALY_RATE):
    """Table de faits brute (sinistres/contrats) — grain d'un événement par
    ligne, ce qui manquait pour construire un vrai fact_claims à l'étape 3.
    Anomalies orientées règles métier (pas juste format), pour donner
    quelque chose de concret au contrôle d'intégrité référentielle du
    pipeline plutôt qu'au moteur de qualité déclaratif de l'étape 2."""
    rng = _rng()
    societaires = societaires_df.to_dict("records")
    adhesion_par_societaire = dict(zip(societaires_df["numero_societaire"], societaires_df["date_adhesion"]))
    rows = []
    for i in range(n):
        soc = rng.choice(societaires)
        adhesion = date.fromisoformat(soc["date_adhesion"])
        borne_haute = date(2026, 8, 12)
        jours_possibles = max((borne_haute - adhesion).days, 1)
        d_sinistre = adhesion + timedelta(days=rng.randint(0, jours_possibles))

        montant_declare = round(rng.uniform(50, 15000), 2)
        statut = rng.choice(STATUTS_SINISTRE)
        montant_rembourse = round(montant_declare * rng.uniform(0.3, 0.95), 2) if statut == "Remboursé" else 0.0

        rows.append({
            "sinistre_id": f"SIN-{700000 + i}",
            "numero_societaire": soc["numero_societaire"],
            "date_sinistre": d_sinistre.isoformat(),
            "type_sinistre": rng.choice(TYPES_SINISTRE),
            "montant_declare": montant_declare,
            "montant_rembourse": montant_rembourse,
            "statut_sinistre": statut,
        })

    df = pd.DataFrame(rows)

    n_anom = int(n * anomaly_rate)
    idx_anom = df.sample(n=n_anom, random_state=SEED).index
    for j, i in enumerate(idx_anom):
        kind = j % 4
        if kind == 0:
            # Référence orpheline : sociétaire inexistant (contrat jamais créé ou déjà purgé)
            df.loc[i, "numero_societaire"] = f"SOC-{900000 + j}"
        elif kind == 1:
            # Remboursement supérieur au montant déclaré (incohérence métier)
            df.loc[i, "montant_rembourse"] = round(df.loc[i, "montant_declare"] * rng.uniform(1.1, 1.5), 2)
        elif kind == 2:
            # Sinistre déclaré avant la date d'adhésion du sociétaire
            adhesion_soc = date.fromisoformat(adhesion_par_societaire[df.loc[i, "numero_societaire"]])
            df.loc[i, "date_sinistre"] = (adhesion_soc - timedelta(days=rng.randint(30, 400))).isoformat()
        elif kind == 3:
            # Montant déclaré négatif (saisie erronée)
            df.loc[i, "montant_declare"] = -abs(df.loc[i, "montant_declare"])

    return df


def main():
    out_dir = Path(__file__).resolve().parent.parent / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    df_societaires = generate_societaires()
    out_path = out_dir / "societaires_bruts.csv"
    df_societaires.to_csv(out_path, index=False, encoding="utf-8")
    print(f"{len(df_societaires)} sociétaires générés -> {out_path}")
    print(f"Doublons numero_societaire : {df_societaires['numero_societaire'].duplicated().sum()}")
    print(f"Emails invalides (sans @) : {(~df_societaires['email'].str.contains('@')).sum()}")

    df_sinistres = generate_sinistres(df_societaires)
    out_path_sinistres = out_dir / "sinistres_bruts.csv"
    df_sinistres.to_csv(out_path_sinistres, index=False, encoding="utf-8")
    print(f"\n{len(df_sinistres)} sinistres générés -> {out_path_sinistres}")
    orphelins = ~df_sinistres["numero_societaire"].isin(df_societaires["numero_societaire"])
    print(f"Sinistres orphelins (sociétaire inexistant) : {orphelins.sum()}")


if __name__ == "__main__":
    main()
