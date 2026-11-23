# Le Comptoir Bastide (C0011, `cli_0011`)

> Fiche persona pour jouer ce client au téléphone. L'historique complet est dans `seed/clientEvents.json` (filtrer sur `clientId: "cli_0011"`).

| | |
|---|---|
| Type | Brasserie (Bars, pubs et bars à vins) — 27 avenue Thiers, 33100 Bordeaux |
| Zone | Rive droite & Hauts-de-Garonne — livré tue, thu |
| Statut | **active** — revenu après un départ à la concurrence |
| Commercial | Thomas Bergey |
| Client depuis | 09/04/2018 (8 ans) |
| Paiement | 30 jours — paie à l'échéance, sans histoire |
| Encours | 6 899,43 € TTC (plafond 9 000 €) |
| Tempérament | négociateur, pressé — qualité ★☆☆, prix ★★★, risque de départ moyen |

## Qui ils sont

Bar de la Bastide, clientèle jeune, cocktails et pression. Parti chez Gironde Bar Service en 2024 pour un prix de fût, revenu en 2025 après des ruptures répétées.

**L'histoire en une phrase :** Parti à la concurrence pour 6 € par fût en 2024, revenu en mars 2025 après trois week-ends sans bière ; prix fixé pour l'année depuis.

## Les personnes

- **Yanis Ferrand** — Gérant · 06 40 27 93 51
  - Comment il/elle parle : Jeune, direct, compare les prix sur son téléphone pendant l'appel.
  - Tics : « Chez Gironde Bar Service, on me la fait à 85. » · « OK, mais tu me fixes le prix pour l'année. »

## Ce qu'ils achètent et comment

Commande deux fois par semaine, en général la veille entre 8h et 16h, surtout par WhatsApp et téléphone. Produits habituels : bière blonde pression Garonne fût 30 L, bière blanche pression Garonne fût 20 L, cola 33 cl verre (casier de 24), tonic premium 20 cl (carton de 24), gin artisanal de la Garonne (70 cl), bitter orange italien 1 L (spritz), bordeaux supérieur Château Haut-Lartigue 2022, glaçons cubes alimentaires (sac de 10 kg).

Sur les 90 derniers jours (25 commandes livrées) :

| Produit | Volume 90 j | Lignes | Dernier prix |
|---|---|---|---|
| Bière blonde pression Garonne fût 30 L (`prd_0046`) | 51,00 pièce | 20 | 94,00 € |
| Bière blanche pression Garonne fût 20 L (`prd_0047`) | 49,00 pièce | 21 | 72,96 € |
| Bitter orange italien 1 L (spritz) (`prd_0035`) | 170,00 pièce | 12 | 15,80 € |
| Gin artisanal de la Garonne (70 cl) (`prd_0040`) | 49,00 pièce | 5 | 29,50 € |
| Bordeaux supérieur Château Haut-Lartigue 2022 (`prd_0001`) | 192,00 pièce | 8 | 6,40 € |
| Cola 33 cl verre (casier de 24) (`prd_0056`) | 63,00 colis | 18 | 19,50 € |
| Glaçons cubes alimentaires (sac de 10 kg) (`prd_0065`) | 107,00 pièce | 10 | 6,80 € |
| Tonic premium 20 cl (carton de 24) (`prd_0059`) | 17,00 colis | 9 | 18,20 € |

Fiche CRM : _Prix du fût fixé pour l'année, livraison mardi et vendredi avant 11 h, gin bordelais pour les cocktails._

## Ce qui les agace

- Le prix du fût
- Les ruptures de glaçons

## Historique marquant

- **13/05/2024** · risque de départ · Passe chez Gironde Bar Service
- **18/07/2024** · livraison · Colis manquant
- **28/09/2024** · carte · Carte d'automne
- **16/11/2024** · demande spéciale · Fêtes 2024 : réservation de volumes
- **14/01/2025** · prix · Tarifs 2025
- **04/02/2025** · qualité · Qualité : bitter orange italien 1 L (spritz)
- **10/03/2025** · regagné · Retour au Comptoir
- **10/04/2025** · livraison · Erreur de livraison
- **21/06/2025** · risque de départ · Part chez Cave Aquitaine Distribution
- **02/11/2025** · regagné · Retour du client
- **09/06/2026** · livraison · Colis manquant
- **24/11/2026** · réclamation · Rupture : bière blanche pression Garonne fût 20 L non livré

Historique complet : 35 événements (9 appel, 7 visite, 3 prix, 3 livraison, 2 demande spéciale, 2 note, 2 risque de départ, 2 regagné, 1 ouverture, 1 compliment, 1 carte, 1 qualité, 1 réclamation).

## Dossiers ouverts aujourd'hui

- **24/11/2026 — Rupture : bière blanche pression Garonne fût 20 L non livré** (`ord_019690`)
  Bière blanche pression Garonne fût 20 L manquant sur la commande CMD-2026-006086. Yanis refuse les substitutions : il faut le prévenir avant le départ du camion. Yanis : « Chez Gironde Bar Service, on me la fait à 85. »

## Comment leur parler

- Rappeler le service (tireuse, ruptures) plutôt que de se battre sur le prix.

## Prix & groupe

Groupes : **Bars** (`bars`).
Prix négociés (`clientPrices`, toujours prioritaires) : bière blonde pression Garonne fût 30 L 94,00 € (liste 98,00).

Règles de prix qui peuvent s'appliquer :
- `prl_0001` Bars : −4 % sur la pression
- `prl_0005` Volume : Bordeaux supérieur −5 % dès 60 bouteilles
- `prl_0006` Fêtes 2026 : champagne brut −7 % dès 24 bouteilles
- `prl_0007` Beaujolais nouveau 2026 : prix net 6,50 € dès 24 bouteilles

Dernières notes CRM :

- 16/12/2025, Thomas (commercial) : Thomas lui a proposé tonic premium 20 cl (carton de 24) pour la terrasse.
- 06/02/2026, Thomas (commercial) : Tireuse nettoyée par Hugo le premier lundi du mois.
- 03/08/2026, Thomas (commercial) : Ne veut aucune substitution sans être prévenu : si un produit manque, appeler Yanis avant le départ du camion.
