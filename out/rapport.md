# Rapport de corroboration RH / Temps

Ce rapport est généré par `run.py`. Les fichiers d'entrée n'ont pas été modifiés (empreintes SHA-256 ci-dessous).

## Synthèse

| Verdict | Nombre | Part |
|---|---|---|
| ANOMALIE | 7 | 30% |
| ANOMALIE PROBABLE (à valider) | 3 | 13% |
| ÉCART JUSTIFIÉ | 2 | 9% |
| CONFORME | 11 | 48% |
| Total | 23 | 100% |

## Écarts systématiques (à confirmer, pas des erreurs par ligne)

Une règle qui échoue sur presque toutes les lignes indique un effet de génération ou d'anonymisation du jeu, pas une erreur par dossier.

| Règle | Lignes en écart | Lignes évaluées |
|---|---|---|
| R13 | 22 | 22 |

## Anomalies à investiguer

| Matricule | Poste | Type affectation | Verdict | Écarts à investiguer | Résumé |
|---|---|---|---|---|---|
| 1545850 | 45985 | A | ANOMALIE |  | Affectation A (poste 45985) absente de la cible. Aucune règle de filtrage dans le mapping ne l'exclut. |
| 2762457 | 30106 | P | ANOMALIE | contractTypeCode | écarts : contractTypeCode; systématique : contactEmail, positionName |
| 3241002 | 88622 | P | ANOMALIE | siteName | écarts : siteName; systématique : contactEmail, positionName; justifié : assignmentStartDate |
| 3712987 | 86337 | P | ANOMALIE | contractTypeCode, dailyHoursOverride, weeklyHoursOverride | écarts : contractTypeCode, dailyHoursOverride, weeklyHoursOverride; systématique : contactEmail, positionName |
| 4625374 | 43478 | P | ANOMALIE | contractTypeCode | écarts : contractTypeCode; systématique : contactEmail, positionName |
| 6035643 | 47056 | P | ANOMALIE | siteName | écarts : siteName; systématique : contactEmail, positionName |
| 7254364 | 14553 | P | ANOMALIE | contractTypeCode | écarts : contractTypeCode; systématique : contactEmail, positionName |
| 2911996 | 12548 | P | ANOMALIE PROBABLE (à valider) | dailyHoursOverride, weeklyHoursOverride | écarts : dailyHoursOverride, weeklyHoursOverride; systématique : contactEmail, positionName; justifié : detailedStatus, statusReasonCode |
| 4402456 | 26586 | P | ANOMALIE PROBABLE (à valider) | dailyHoursOverride, weeklyHoursOverride | écarts : dailyHoursOverride, weeklyHoursOverride; systématique : contactEmail, positionName; justifié : assignmentStartDate |
| 7683990 | 15514 | P | ANOMALIE PROBABLE (à valider) | dailyHoursOverride, weeklyHoursOverride | écarts : dailyHoursOverride, weeklyHoursOverride; systématique : contactEmail, positionName |

Le détail par champ, avec la référence au mapping, la valeur attendue et la preuve, est dans `rapport_corroboration_details.csv` et dans l'onglet *Détail des règles* du classeur Excel.

## Écarts justifiés (conversion par table ou encodage)

| Matricule | Poste | Type affectation | Résumé |
|---|---|---|---|
| 7603160 | 83560 | P | systématique : contactEmail, positionName; justifié : detailedStatus, statusReasonCode |
| 9989151 | 31109 | P | systématique : contactEmail, positionName; justifié : assignmentStartDate |

## Cas conformes

| Matricule | Poste | Type affectation |
|---|---|---|
| 1545850 | 35342 | P |
| 2173396 | 69289 | P |
| 2648214 | 73721 | P |
| 2747515 | 63970 | P |
| 4880692 | 35161 | P |
| 6783031 | 23999 | P |
| 7070325 | 81864 | P |
| 7683990 | 23841 | S |
| 7683990 | 98689 | S |
| 8142123 | 26800 | P |
| 8644330 | 67970 | P |

## Démonstration des trois types de cas

### 1. Cas conforme : matricule 1545850, affectation P, poste 35342
Verdict : **CONFORME**. systématique : contactEmail, positionName
Tous les champs contrôlés concordent. Le seul écart restant est systématique (voir ci-dessus).

### 2. Écart justifié : matricule 7603160, affectation P, poste 83560
Verdict : **ÉCART JUSTIFIÉ**. systématique : contactEmail, positionName; justifié : detailedStatus, statusReasonCode

| Règle | Champ cible | Valeur attendue | Valeur cible | Statut | Explication | Référence mapping |
|---|---|---|---|---|---|---|
| R22 | detailedStatus | Absence complète | Absence complÃ¨te | Écart justifié | Valeur identique après correction d'encodage ('Absence complÃ¨te' lu comme 'Absence complète'). | Mapping.xlsx > Mapping (Situation d'emploi selon le code de traitement des accès) |
| R24 | statusReasonCode | 170 | 170 | Écart justifié | Conversion par table de référence : code source 807 → valeur cible 170 (Mapping.xlsx > Jointure - Motif des situations ; Motif de la situation d'emploi.xlsx). | Mapping.xlsx > Mapping > ligne 19 (Code de situation d'emploi Remphor (table des motifs)) |

### 3. Vraie anomalie : matricule 2762457, affectation P, poste 30106
Verdict : **ANOMALIE**. écarts : contractTypeCode; systématique : contactEmail, positionName

| Règle | Champ cible | Valeur attendue | Valeur cible | Statut | Explication | Référence mapping |
|---|---|---|---|---|---|---|
| R15 | contractTypeCode | JWN | WHX | Écart | Valeur cible différente de la valeur attendue selon la règle. Valeur attendue pour un autre dossier (4625374) : probable inversion lors du transfert. | Mapping.xlsx > Mapping > ligne 24 (Type d'employé (CatégorieEmploi + PERM_IND + FT_IND)) |


## Champs non contrôlés

Champs présents dans les extractions mais absents du mapping, donc non corroborés. Le mapping est la seule référence.

| Système | Champ | Raison |
|---|---|---|
| A - RH | IntituléPoste | Hors mapping ou sans règle de corroboration |
| A - RH | LibelléÉchelleSalariale | Hors mapping ou sans règle de corroboration |
| A - RH | LibelléImputation | Hors mapping ou sans règle de corroboration |
| A - RH | CodeStatutEmploi | Hors mapping ou sans règle de corroboration |
| A - RH | LibelléRaisonStatut | Hors mapping ou sans règle de corroboration |
| A - RH | DateEffetRaison | Hors mapping ou sans règle de corroboration |
| A - RH | IdentifiantResponsable | Hors mapping ou sans règle de corroboration |
| A - RH | NomResponsable | Hors mapping ou sans règle de corroboration |
| A - RH | CodeQuart | Hors mapping ou sans règle de corroboration |
| B - Temps | activityStatus | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_01 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_02 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_03 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_04 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_05 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_06 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_07 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_08 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_09 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_10 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_11 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_12 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_13 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_14 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_15 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_16 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_17 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_18 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_19 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_20 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_21 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_22 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_23 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_24 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_25 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_26 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_27 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_28 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_29 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_30 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_31 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_32 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_33 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_34 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_35 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_36 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_37 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_38 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_39 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_40 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_41 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_42 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_43 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_44 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_45 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_46 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_47 | Hors mapping ou sans source correspondante |
| B - Temps | customAttribute_48 | Hors mapping ou sans source correspondante |
| B - Temps | termStartDate | Hors mapping ou sans source correspondante |
| B - Temps | termEndDate | Hors mapping ou sans source correspondante |
| B - Temps | wageOverrideAmount | Hors mapping ou sans source correspondante |
| B - Temps | wageMultiplierFactor | Hors mapping ou sans source correspondante |
| B - Temps | externalReferenceId | Hors mapping ou sans source correspondante |

## Intégrité des entrées

| Fichier | SHA-256 avant | SHA-256 après | Inchangé |
|---|---|---|---|
| Employe_Source_Anonymise_VF.xlsx | 4f825d17938a8170ea1ed2986b12ed240987430984b3693b993bd8f2f290f5b6 | 4f825d17938a8170ea1ed2986b12ed240987430984b3693b993bd8f2f290f5b6 | True |
| Employe_Destination_Anonymise_VF.xlsx | 67c4d64b4a11e566bc4962da8a50562b47f394c27a3555476117b0a702b10717 | 67c4d64b4a11e566bc4962da8a50562b47f394c27a3555476117b0a702b10717 | True |
| Mapping.xlsx | 6e7e618d6efbc67576056de610f91b8f47beebbbf59873ffe797f3d305a677ee | 6e7e618d6efbc67576056de610f91b8f47beebbbf59873ffe797f3d305a677ee | True |
| Motif de la situation d'emploi.xlsx | 5d143df7ee15e3532eb01469a5a442bc87d1a80edc9cbb3d90bcb246f9e0973b | 5d143df7ee15e3532eb01469a5a442bc87d1a80edc9cbb3d90bcb246f9e0973b | True |
| détail_du_poste.xlsx | ab142775628bc16d4239b01d94733f9f094004ff9c36db33bdc190862ab18b6c | ab142775628bc16d4239b01d94733f9f094004ff9c36db33bdc190862ab18b6c | True |
