# PROMPT LOG — Comment j'ai construit ce projet avec l'IA

> Ce fichier documente ma méthode de travail réelle avec l'IA (Claude).
> Je n'ai pas de background développeur. Ce log prouve que la valeur n'est pas dans le code — elle est dans la capacité à cadrer un problème, vérifier ce qui est produit plutôt que de le prendre pour argent comptant, et rester rigoureuse sur ce qui est vrai ou non.

---

## Contexte de départ

Ce projet vient d'un poste hybride Business Analyst Engineer / Data Quality Manager observé dans le secteur assurance/mutuelle — **pas d'une mission que j'ai effectuée**. J'ai donné un brief détaillé (structure de dossiers, stack, 4 étapes) et demandé une construction pas à pas, une étape validée avant de passer à la suivante, plutôt qu'un livrable d'un bloc.

## Étape 1 — Génération de données

Générateur de 1000 sociétaires simulés avec 4 familles d'anomalies contrôlées (emails invalides, dates de naissance incohérentes, doublons de numéro de sociétaire, téléphones mal saisis).

**Bug trouvé pendant le test de l'étape 2, corrigé rétroactivement à l'étape 1** : la tranche de date de naissance couvrait 1945 à 2025, ce qui générait des sociétaires de moins de 18 ans sans rapport avec les anomalies volontaires — ces faux mineurs polluaient le score d'Exactitude (93,8/100 au lieu de 98,3/100 une fois corrigé). Resserré à une tranche d'âge adulte plausible (18-85 ans), régénéré, revérifié.

## Étape 2 — Moteur de qualité déclaratif & anonymisation

**Le point sur lequel j'ai insisté, différent des projets précédents du portfolio** : les règles de qualité devaient être lues depuis un fichier YAML (`config/rules.yaml`), pas codées en dur en Python — cohérent avec le positionnement Business Analyst du poste visé, où une règle métier doit pouvoir être ajustée sans toucher au code. L'IA a construit un petit registre de fonctions de règles (`not_null`, `unique`, `format_email`, `age_plausible`, etc.) invoquées par nom depuis le YAML.

`anonymizer.py` pseudonymise le nom via un hash dérivé du **numéro de sociétaire** (jamais du nom lui-même, pour ne rien faire fuiter dans l'empreinte), masque téléphone et IBAN, et n'anonymise que les lignes déjà validées par le moteur de qualité.

## Étape 3 — Pipeline & entrepôt

Le brief d'origine demandait un `fact_claims` (sinistres/contrats), mais l'étape 1 n'avait généré que des sociétaires — aucune table de faits n'existait encore pour lui donner un grain réel. L'IA a signalé le manque plutôt que d'improviser une table de faits creuse, et complété `generator.py` avec une table `sinistres` (600 lignes), avec des anomalies orientées règles métier cette fois (référence orpheline, remboursement supérieur au montant déclaré, sinistre antérieur à l'adhésion) plutôt que des anomalies de format.

Pipeline SQL en couches (staging → marts) via DuckDB, même pattern que le projet Unified Customer Analytics du portfolio : `fact_claims` garde tous les sinistres visibles pour l'audit, avec des colonnes booléennes d'écart plutôt qu'un filtrage silencieux.

**Point de vigilance découvert en testant, pas anticipé au départ** : les sinistres orphelins comptabilisés (59) sont plus nombreux que les 12 volontairement injectés — le reste provient de sociétaires eux-mêmes rejetés par le moteur de qualité de l'étape 2, donc absents du référentiel validé. Ce n'est pas une erreur, c'est un effet en cascade réaliste (un sinistre référence un dossier que la qualité amont a déjà invalidé) — gardé et expliqué tel quel plutôt que masqué.

## Étape 4 — Dashboard

Streamlit, repris du même design (palette, structure sidebar/onglets/KPI) que le projet Unified Customer Analytics pour rester cohérent visuellement sur le portfolio. 4 onglets : Data Health Scorecard, Anomalies détectées (avec preuve visuelle avant/après du masquage RGPD sur nom/téléphone/IBAN), exploration de l'entrepôt, dictionnaire de données interactif filtrable par champ PII.

---

## Ce que ce projet prouve (pour un client ou un recruteur)

| Compétence démontrée | Preuve dans ce projet |
|---|---|
| Data Quality Management | Moteur de règles déclaratif, Data Health Score à 3 axes, rien codé en dur |
| Conformité RGPD appliquée | Anonymisation ciblée sur les champs PII identifiés, dictionnaire de données avec classification RGPD par champ |
| Analytics Engineering | Pipeline SQL en couches, entrepôt en étoile DuckDB, écarts jamais masqués en silence |
| Rigueur méthodologique | Bug de tranche d'âge trouvé et corrigé après coup, manque de grain pour `fact_claims` signalé avant de construire à côté |
| Vérification, pas confiance aveugle | Chaque étape testée en local avant de passer à la suivante |

---

## Ma conclusion

> Je ne suis pas développeuse. Mais je sais repérer quand un livrable manque de matière pour tenir sa promesse (le grain de `fact_claims`), et je vérifie chaque étape avant de la considérer terminée plutôt que de faire confiance au premier résultat qui s'affiche.

*Gisèle Metouck — Consultante Data Steward & Gouvernance*
