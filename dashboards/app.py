"""Enterprise Data Quality & Pipeline Automation Platform — POC personnel.
Génération de sociétaires/sinistres simulés, moteur de qualité déclaratif
(YAML), anonymisation RGPD, entrepôt DuckDB en étoile, et ce dashboard :
score de santé, détail des anomalies, dictionnaire de données interactif.
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
sys.path.insert(0, str(SRC_DIR))

import anonymizer
import generator
import pipeline as data_pipeline
import quality_engine

C_PRIMARY = "#0071E3"
C_GOOD    = "#34C759"
C_WARNING = "#FF9F0A"
C_DANGER  = "#FF3B30"
C_SURF    = "#F5F5F7"
C_TEXT    = "#1D1D1F"
C_MUTED   = "#6E6E73"
C_BORDER  = "#E8E8ED"

STATUT_COLORS = {"OK": C_GOOD, "ALERTE": C_WARNING, "CRITIQUE": C_DANGER}

CHART_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=C_TEXT, family="Inter, -apple-system, sans-serif", size=13),
    margin=dict(l=20, r=20, t=40, b=20),
)

st.set_page_config(page_title="Data Quality & Pipeline Automation", page_icon="🛡️",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
html, body, [class*="css"] { font-family:'Inter',-apple-system,sans-serif; }
div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
.stTabs [aria-selected="true"] { font-weight: 700; }
</style>
""", unsafe_allow_html=True)


def score_color(v):
    return C_GOOD if v >= 95 else C_WARNING if v >= 85 else C_DANGER


@st.cache_data
def load_all():
    df_soc = generator.generate_societaires()
    resultats = quality_engine.run_quality_suite(df_soc)
    df_soc_valides = quality_engine.lignes_valides(df_soc, resultats)
    df_anon = anonymizer.anonymize_societaires(df_soc_valides)

    df_sinistres = generator.generate_sinistres(df_soc)
    tables, execution_log, con = data_pipeline.run_pipeline(df_anon, df_sinistres)
    con.close()

    scorecard = quality_engine.data_health_scorecard(resultats)
    df_resultats = quality_engine.resultats_to_dataframe(resultats)

    with open(CONFIG_DIR / "data_dictionary.yaml", encoding="utf-8") as f:
        dictionnaire = yaml.safe_load(f)["champs"]

    return {
        "df_soc": df_soc, "df_soc_valides": df_soc_valides, "df_anon": df_anon,
        "df_sinistres": df_sinistres, "tables": tables, "execution_log": execution_log,
        "scorecard": scorecard, "df_resultats": df_resultats, "dictionnaire": dictionnaire,
    }


data = load_all()
scorecard = data["scorecard"]
df_resultats = data["df_resultats"]
fact_claims = data["tables"]["fact_claims"]
dim_societaires = data["tables"]["dim_societaires"]

with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:12px 0;'>"
        "<div style='font-size:1.8rem;'>🛡️</div>"
        f"<div style='color:{C_PRIMARY};font-size:1.0rem;font-weight:700;'>Data Quality Platform</div>"
        f"<div style='color:{C_MUTED};font-size:0.72rem;'>Gouvernance · RGPD · Entrepôt en étoile</div>"
        "</div>", unsafe_allow_html=True)
    st.markdown(f"<hr style='border-color:{C_BORDER};'>", unsafe_allow_html=True)

    st.markdown(
        f"<div style='background:{C_SURF};border-radius:8px;padding:10px;font-size:0.75rem;color:{C_MUTED};'>"
        "⚠️ <strong>Projet personnel (POC)</strong><br>"
        "Je voulais comprendre comment un poste hybride Business Analyst / Data Quality Manager "
        "gère la fiabilisation d'une base de sociétaires secteur assurance/mutuelle, de bout en "
        "bout : qualité, RGPD, entrepôt, pilotage. Données entièrement simulées, aucune personne "
        "ni organisme réel."
        "</div>", unsafe_allow_html=True)
    st.caption("Construit avec l'IA — Gisèle Metouck")
    st.caption("[GitHub](https://github.com/Kingdmfncr)")

st.title("Data Quality & Pipeline Automation Platform")
st.caption("Data Health Scorecard, détail des anomalies, entrepôt en étoile (DuckDB) et dictionnaire de données interactif.")

c1, c2, c3 = st.columns(3)
c1.metric("Complétude", f"{scorecard['Complétude']}%")
c2.metric("Exactitude", f"{scorecard['Exactitude']}%")
c3.metric("Fraîcheur", f"{scorecard['Fraîcheur']}%")

tabs = st.tabs(["Data Health Scorecard", "Anomalies détectées", "Entrepôt (dim / fact)", "Dictionnaire de données"])

with tabs[0]:
    fig = go.Figure(go.Bar(
        x=list(scorecard.values()), y=list(scorecard.keys()), orientation="h",
        marker_color=[score_color(v) for v in scorecard.values()],
    ))
    fig.update_layout(title="Data Health Scorecard (%)", height=280, xaxis_range=[0, 100], **CHART_DEFAULTS)
    st.plotly_chart(fig, use_container_width=True, key="chart_scorecard")

    rep_statut = df_resultats["Statut"].value_counts()
    fig2 = go.Figure(go.Pie(labels=rep_statut.index, values=rep_statut.values, hole=0.55,
                            marker=dict(colors=[STATUT_COLORS[s] for s in rep_statut.index])))
    fig2.update_layout(title="Répartition des règles par statut", height=300, **CHART_DEFAULTS)
    st.plotly_chart(fig2, use_container_width=True, key="chart_statut_regles")

    st.caption("Statut d'exécution du pipeline SQL (staging → marts) :")
    echecs = data["execution_log"][data["execution_log"]["statut"] == "Échec"]
    if not echecs.empty:
        st.error(f"⚠️ {len(echecs)} modèle(s) en échec.")
    else:
        st.success("✅ Tous les modèles se sont exécutés avec succès.")
    st.dataframe(data["execution_log"], use_container_width=True, hide_index=True)

with tabs[1]:
    st.caption("Règles déclarées dans `config/rules.yaml` (aucune codée en dur) — sociétaires.")
    st.dataframe(df_resultats, use_container_width=True, hide_index=True)
    st.info(f"{len(data['df_soc_valides'])} sociétaires sur {len(data['df_soc'])} exploités en aval "
            f"— les lignes en écart critique sont exclues, jamais corrigées silencieusement.")

    st.markdown("**Écarts sur les sinistres (`fact_claims`)** — tous visibles, jamais filtrés en amont :")
    d1, d2, d3 = st.columns(3)
    d1.metric("Sociétaire inexistant", int((~fact_claims["societaire_existe"]).sum()))
    d2.metric("Sinistre avant adhésion", int(fact_claims["sinistre_avant_adhesion"].sum()))
    d3.metric("Remboursement incohérent", int(fact_claims["remboursement_incoherent"].sum()))
    ecarts = fact_claims[
        (~fact_claims["societaire_existe"])
        | fact_claims["sinistre_avant_adhesion"]
        | fact_claims["remboursement_incoherent"]
    ]
    st.dataframe(ecarts, use_container_width=True, hide_index=True)

    st.markdown("**Preuve du masquage RGPD (nom / téléphone / IBAN)** — avant / après anonymisation :")
    avant = data["df_soc_valides"][["numero_societaire", "nom", "telephone", "iban"]].head(5)
    apres = data["df_anon"][["numero_societaire", "nom", "telephone", "iban"]].head(5)
    comparaison = avant.merge(apres, on="numero_societaire", suffixes=(" (brut)", " (anonymisé)"))
    st.dataframe(comparaison, use_container_width=True, hide_index=True)

with tabs[2]:
    st.caption(f"`dim_societaires` : {len(dim_societaires)} lignes — {len(fact_claims)} lignes dans `fact_claims`.")
    sous_tab_dim, sous_tab_fact = st.tabs(["dim_societaires", "fact_claims"])
    with sous_tab_dim:
        st.dataframe(dim_societaires, use_container_width=True, hide_index=True)
    with sous_tab_fact:
        st.dataframe(fact_claims, use_container_width=True, hide_index=True)

with tabs[3]:
    st.caption("Dictionnaire de données — `config/data_dictionary.yaml`, classification RGPD par champ.")
    afficher_pii_uniquement = st.checkbox("Afficher uniquement les champs PII")

    lignes = []
    for champ, meta in data["dictionnaire"].items():
        lignes.append({
            "Champ": champ, "Type": meta["type"], "Description": meta["description"],
            "PII": "🔴 Oui" if meta["pii"] else "🟢 Non", "Traitement RGPD": meta["rgpd_action"],
        })
    df_dict = pd.DataFrame(lignes)
    if afficher_pii_uniquement:
        df_dict = df_dict[df_dict["PII"] == "🔴 Oui"]
    st.dataframe(df_dict, use_container_width=True, hide_index=True)
