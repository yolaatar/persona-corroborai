# Script de démonstration (3 minutes)

Objectif : montrer les trois types de cas exigés (conforme, écart justifié, vraie anomalie), la preuve de chaque verdict, et la gestion des cas ambigus.

## 1. Lancer (30 s)

```bash
python run.py --data ../corroborai-participants --out out
open out/index.html
```

Dire : les extractions sont ouvertes en lecture seule, et les empreintes SHA-256 prouvent qu'elles n'ont pas changé (section *Intégrité* du rapport).

## 2. Vue d'ensemble (30 s)

Montrer le compteur : 23 lignes source, 11 conformes, 2 écarts justifiés, 3 anomalies probables, 7 anomalies. Expliquer qu'un écart systématique (courriel, libellé de rôle) n'est pas compté comme erreur par dossier : c'est un effet du jeu, à confirmer.

## 3. Cas conforme (30 s)

Matricule **1545850**, affectation P. Tous les champs contrôlés concordent. Le seul point est l'écart systématique sur le courriel et le libellé de rôle.

## 4. Écart justifié (45 s)

Matricule **7603160**, affectation P.
- `statusReasonCode` : la source porte 807, la cible 170. C'est une conversion documentée par la table des motifs : **justifié**.
- `detailedStatus` : « Absence complÃ¨te » est un problème d'encodage. La valeur est correcte : **justifié**.

## 5. Vraie anomalie (45 s)

Matricule **2762457**, affectation P.
- `contractTypeCode` attendu JWN (catégorie V, permanent, temps plein), cible WHX.
- La preuve est dans le dossier **4625374** : sa valeur attendue est WHX, sa cible JWN. Les deux dossiers ont leurs valeurs échangées : **inversion probable pendant le transfert**.

## 6. Cas ambigu, arbitré (30 s)

Matricule **2911996**, affectation P.
- Horaires : source 35 h/sem, cible 40 h/sem. La cible reprend la valeur du détail de poste, que le mapping n'utilise pas pour ce champ.
- Verdict **ANOMALIE PROBABLE (à valider)**, confiance 0,7. Ce n'est pas une décision automatique : un humain tranche.
- Pour le cas 3712987 (source vide), le verdict est **À ARBITRER**, confiance 0,5.

## 7. Limites (20 s)

- Le moteur ne lit que les champs du mapping.
- L'arbitrage repose sur des preuves croisées, pas sur un modèle de langage. Aucune donnée ne sort de la machine.
- La date d'entrée cible est la règle transformée, voulue selon les organisateurs : elle est justifiée et non une anomalie.

## Question possible du jury : « Et si les données changent ? »

Les tests de perturbation injectent une erreur de contrat, une affectation supprimée, un dossier orphelin et une entrée de motif manquante dans une copie des données : chaque cas est détecté (`pytest -q`, 15 tests).
