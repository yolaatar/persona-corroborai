# CorroborAI : détection explicable des écarts RH / Temps

Compare l'extraction du Système A (RH) à celle du Système B (Temps), applique les règles du fichier de mapping, arbitre les cas ambigus et produit un rapport où chaque verdict porte sa justification et ses preuves.

Les fichiers d'entrée sont ouverts en lecture seule. Leurs empreintes SHA-256 sont vérifiées avant et après chaque exécution.

## Démarrage

```bash
pip install -r requirements.txt
python run.py --data ../corroborai-participants --out out
python -m pytest -q                      # tests de non-régression et de perturbation (15)
```

Sortie dans `out/` (un exemple généré à partir des extractions du défi est dans le dépôt, autorisé par les organisateurs) :

| Fichier | Contenu |
|---|---|
| `index.html` | Visionneuse autonome (un seul fichier, hors ligne) : filtres par verdict, recherche, justification et preuve par champ |
| `rapport.md` | Synthèse, anomalies, démonstration des trois types de cas, champs non contrôlés, intégrité |
| `rapport_corroboration.xlsx` | Classeur : synthèse, verdicts par ligne, anomalies, détail des règles, champs non contrôlés, intégrité |
| `rapport_corroboration_details.csv` | Un enregistrement par champ contrôlé, avec référence mapping, valeurs, statut, preuves (exportable) |
| `rapport_corroboration_verdicts.csv` | Un verdict par dossier |
| `run.json` | Empreintes des entrées et compteurs |

## Résultats sur le jeu fourni

| Verdict | Lignes |
|---|---|
| ANOMALIE | 7 |
| ANOMALIE PROBABLE (à valider) | 3 |
| ÉCART JUSTIFIÉ | 2 |
| CONFORME | 11 |

Les 23 lignes source sont rapprochées de 22 lignes cible. Une affectation temporaire (`TypeAffectation = A`) est absente de la cible et sort en anomalie.

## Légende des verdicts

| Verdict | Signification |
|---|---|
| **ANOMALIE** | Écart qu'une règle tranche sans ambiguïté, ou enregistrement absent d'un côté. À investiguer. |
| **ANOMALIE PROBABLE (à valider)** | Preuves croisées fortes (confiance ≥ 0,6), mais la décision revient à un humain. |
| **À ARBITRER** | Preuves insuffisantes (confiance < 0,6). |
| **ÉCART JUSTIFIÉ** | Différence expliquée par une règle documentée : conversion par table de référence, encodage. |
| **ÉCART SYSTÉMATIQUE (à confirmer)** | Même règle en échec sur presque toutes les lignes. Ce n'est pas une erreur par dossier. Présenté au niveau du jeu de données. |
| **CONFORME** | Tous les champs contrôlés concordent. |

## Méthode

1. **Rapprochement** : chaque ligne source est associée à une ligne cible sur matricule + code emploi + date d'effet, avec repli sur matricule + code emploi quand il identifie une seule ligne.
2. **Règles déterministes** (`corroborai/rules.py`) : chaque champ du mapping a une règle. Elle calcule la valeur attendue à partir de la source et cite la ligne de `Mapping.xlsx` correspondante. Exemples :
   - statut « Absence complète » : code de traitement des accès 2, 3, 6 ou 7 ;
   - code de situation Remphor : table `Motif de la situation d'emploi.xlsx`, par exemple 807 → 170 ;
   - type de contrat : catégorie V + permanent + temps plein → JWN ; V + permanent + temps partiel → XFLR ; O → WHX ;
   - courriel : initiale du prénom + nom + 3 derniers chiffres du matricule, sans accents ;
   - libellé de département : code sur 5 caractères + « - » + libellé.
3. **Normalisation** : encodage cassé corrigé (`Absence complÃ¨te`), dates et nombres comparés en valeur.
4. **Écarts systématiques** : une règle qui échoue sur au moins 80 % des lignes (minimum 5) est signalée au niveau du jeu.
5. **Inversions** : si deux dossiers portent chacun la valeur attendue de l'autre, c'est signalé comme inversion probable pendant le transfert.
6. **Arbitrage des cas ambigus** (`corroborai/arbitre.py`) : pour les horaires et la date d'entrée, le module croise le détail de poste, les autres affectations de la personne et la date d'effet la plus récente. Il produit un verdict, une confiance, une explication et les preuves.

## Ce qui est IA, et ce qui ne l'est pas

- **Déterministe** : toutes les règles du mapping, la normalisation, la détection d'inversions et d'écarts systématiques.
- **Arbitrage assisté** : l'arbitre pondère des preuves croisées et produit une confiance. Ce n'est pas un modèle de langage. Il est explicable et reproductible.
- **Pas d'appel à un service externe** : les extractions ne quittent pas la machine. Les consignes interdisent de transmettre des données à un service externe non autorisé. Un LLM pourrait être branché sur l'arbitre si l'organisateur l'approuve. Ce n'est pas le cas aujourd'hui.

## Limites et points à confirmer

- **Règle de date** : le mapping prévoit la date de changement d'unité administrative tirée du détail de poste. La cible ne la reproduit pas pour la plupart des lignes et utilise la date d'entrée source. Le contrôle s'appuie donc sur `DateEntréePoste`. Trois dossiers portent une date égale à la dernière date d'effet du détail : les organisateurs ont confirmé que c'est la règle transformée voulue, donc écart justifié.
- **Libellé de rôle** : le préfixe numérique différent du code emploi est une erreur confirmée par les organisateurs : signalé comme écart systématique.
- **Courriel** : la source ne contient pas l'adresse, donc la règle de génération est testée sur les valeurs cible. Le préfixe `dev-08-v2_` est optionnel (accepté, réponse des organisateurs sur Discord). Les chiffres qui diffèrent de la règle sont une erreur d'anonymisation, confirmée par les organisateurs : signalée comme écart systématique et non comme anomalie.
- **Libellé de rôle** : le préfixe numérique du libellé (`4367-Empl4367` pour le code 6203) ne correspond pas au code emploi sur les 22 lignes. Écart systématique à confirmer, probablement un effet d'anonymisation.
- **Horaires** : le mapping ne prévoit pas que les heures viennent du détail de poste. La cible reprend 40 h dans quatre cas où la source indique 35 h, 36 h, ou rien. Verdict probable, pas certain.
- **Champs non mappés** : `termStartDate`, `activityStatus`, `CodeQuart`, `LibelléImputation` et les autres champs hors mapping ne sont pas corroborés. La liste exacte est dans le rapport.
- **Jeu de test** : les règles sont écrites de façon générique, mais les tests de non-régression portent sur les dossiers fournis.

## Outils, sources et modèles utilisés

- Python 3.11, pandas, openpyxl (lecture et écriture Excel), pytest.
- Sources : `Mapping.xlsx` (correspondances et règles), `Motif de la situation d'emploi.xlsx`, `détail_du_poste.xlsx`, extractions `Employe_Source_Anonymise_VF.xlsx` et `Employe_Destination_Anonymise_VF.xlsx`, `consignes.pdf`.
- Aucun modèle de langage ni service externe n'est utilisé dans l'exécution.
- Le code a été écrit avec l'aide de Claude (Anthropic), à la conception et à l'écriture.

## Structure

```
run.py                    point d'entrée CLI
corroborai/loader.py      lecture seule des extractions, décodage du détail de poste
corroborai/rules.py       règles déterministes, une par champ du mapping
corroborai/engine.py      rapprochement, évaluation, systématiques, inversions, verdicts
corroborai/arbitre.py     arbitrage des cas ambigus
corroborai/report.py      Excel, CSV, Markdown, empreintes
corroborai/viewer.py      visionneuse HTML autonome
tests/test_engine.py      tests de non-régression sur les dossiers fournis
tests/test_robustness.py  tests de perturbation (erreurs injectées dans une copie)
DEMO.md                   script de démonstration pour le jury
```
