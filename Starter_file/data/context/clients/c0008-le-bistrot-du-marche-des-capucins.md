# Le Bistrot du Marché des Capucins (C0008, `cli_0008`)

> Fiche persona pour jouer ce client au téléphone. L'historique complet est dans `seed/clientEvents.json` (filtrer sur `clientId: "cli_0008"`).

| | |
|---|---|
| Type | Brasserie (Brasseries et restaurants traditionnels) — Place des Capucins, 33800 Bordeaux |
| Zone | Bordeaux centre, Chartrons & Saint-Pierre — livré mon, wed |
| Statut | **blocked** — client régulier |
| Commercial | Thomas Bergey |
| Client depuis | 02/06/2014 (12 ans) |
| Paiement | 30 jours — mauvais payeur, compte à risque |
| Encours | 40 281,64 € TTC (plafond 23 000 €) — **2 facture échues : 33 472,85 €** |
| Tempérament | râleur, fidèle — qualité ★★☆, prix ★☆☆, risque de départ faible |

## Qui ils sont

Bistrot historique du marché des Capucins, cuisine du marché et vins de Bordeaux au pichet. Toujours payé en retard mais toujours payé ; bloqué depuis que l'encours a dépassé le plafond.

## Les personnes

- **Joëlle Capdeville** — Gérante · 06 26 51 44 07
  - Comment il/elle parle : Franche, un peu sur la défensive, reconnaît ses retards.
  - Tics : « Je sais, je suis en retard, mais l'été a été mauvais. » · « Laisse-moi jusqu'à la fin du mois. »

## Ce qu'ils achètent et comment

Commande deux fois par semaine, en général la veille entre 10h et 16h, surtout par téléphone et e-mail. Produits habituels : bordeaux supérieur Château Haut-Lartigue 2022, entre-deux-Mers blanc Château Bel-Air-Sauveterre 2025, eau minérale plate 1 L verre (casier de 12), eau gazeuse 1 L verre (casier de 12), bière blonde pression Garonne fût 30 L, bordeaux rouge en bag-in-box 10 L, graves rouge Château Brondelle-Sainte-Croix 2021, eau gazeuse 33 cl verre (casier de 24).

Sur les 90 derniers jours (18 commandes livrées) :

| Produit | Volume 90 j | Lignes | Dernier prix |
|---|---|---|---|
| Bitter orange italien 1 L (spritz) (`prd_0035`) | 298,00 pièce | 11 | 15,17 € |
| Champagne Vauthier-Roussel brut réserve (`prd_0027`) | 162,00 pièce | 10 | 23,50 € |
| Pastis de Marseille 1 L (`prd_0034`) | 136,00 pièce | 10 | 18,50 € |
| Bière blonde pression Garonne fût 30 L (`prd_0046`) | 24,00 pièce | 8 | 94,08 € |
| Bière blonde Garonne 33 cl (carton de 24) (`prd_0050`) | 66,00 colis | 11 | 29,50 € |
| Eau gazeuse 33 cl verre (casier de 24) (`prd_0055`) | 111,00 colis | 13 | 14,80 € |
| Eau minérale plate 1 L verre (casier de 12) (`prd_0053`) | 129,00 colis | 13 | 11,40 € |
| Bordeaux supérieur Château Haut-Lartigue 2022 (`prd_0001`) | 202,00 pièce | 9 | 6,40 € |

Fiche CRM : _Bag-in-box rouge et blanc, eaux, quelques bouteilles pour les habitués. Commande le mardi et le vendredi._

## Ce qui les agace

- Être bloquée après dix ans de fidélité

## Historique marquant

- **15/11/2025** · paiement · Relance : FAC-2025-002218 échue
- **20/11/2025** · demande spéciale · Fêtes 2025 : réservation de volumes
- **10/01/2026** · prix · Tarifs 2026
- **12/02/2026** · paiement · Relance : FAC-2026-000004 échue
- **15/04/2026** · paiement · Relance : FAC-2026-000418 échue
- **14/06/2026** · paiement · Relance : FAC-2026-000961 échue
- **15/07/2026** · qualité · Qualité : eau minérale plate 1 L verre (casier de 12)
- **19/07/2026** · avoir · Avoir qualité : eau minérale plate 1 L verre (casier de 12)
- **13/08/2026** · paiement · Relance : FAC-2026-001542 échue
- **15/10/2026** · paiement · Relance : FAC-2026-002121 échue
- **16/11/2026** · paiement · Compte bloqué pour impayés
- **20/11/2026** · échéancier · Proposition d'échéancier

Historique complet : 62 événements (13 visite, 12 paiement, 10 qualité, 10 demande spéciale, 5 appel, 3 prix, 2 compliment, 2 note, 1 ouverture, 1 carte, 1 retour, 1 avoir, 1 échéancier).

## Dossiers ouverts aujourd'hui

- **15/10/2026 — Relance : FAC-2026-002121 échue** (`inv_008382`)
  Facture FAC-2026-002121 (23 726,82 € TTC) échue le 01/10/2026. Relance par téléphone. Joëlle : « Je ne l'ai pas reçue, renvoyez-la. »
- **16/11/2026 — Compte bloqué pour impayés** (`inv_008382`)
  2 factures échues non réglées pour 33 472,85 € TTC. Livraisons suspendues jusqu'à règlement d'au moins 50 % de l'échu et un échéancier validé.
- **20/11/2026 — Proposition d'échéancier**
  Joëlle propose de payer en 6 fois et demande la reprise des livraisons. En attente de validation par la direction.

## Comment leur parler

- Rester humain : proposer un échéancier, voir avec Martine.

## Prix & groupe

Groupes : **Brasseries** (`brasseries`), **À surveiller** (`a-surveiller`).
Prix négociés (`clientPrices`, toujours prioritaires) : entre-deux-Mers blanc Château Bel-Air-Sauveterre 2025 5,95 € (liste 6,20) ; bière blonde pression Garonne fût 30 L 94,08 € (liste 98,00) ; bitter orange italien 1 L (spritz) 15,17 € (liste 15,80).

Règles de prix qui peuvent s'appliquer :
- `prl_0005` Volume : Bordeaux supérieur −5 % dès 60 bouteilles
- `prl_0006` Fêtes 2026 : champagne brut −7 % dès 24 bouteilles
- `prl_0007` Beaujolais nouveau 2026 : prix net 6,50 € dès 24 bouteilles

Dernières notes CRM :

- 30/12/2025, Thomas (commercial) : Propose un échéancier en trois fois, en attente de validation de Claire.
- 10/05/2026, Thomas (commercial) : Encours au-dessus du plafond, blocage le 16/11.
- 16/11/2026, Martine (comptabilité) : Compte BLOQUÉ pour impayés. 2 factures échues non réglées, la plus ancienne FAC-2026-002121 du 01/09/2026. Encours 40 281,64 € TTC pour un plafond de 23 000,00 €. Reprise des livraisons seulement après un règlement d'au moins 50 % de l'échu et un échéancier validé par la direction.
- 22/11/2026, Thomas (commercial) : Joëlle a rappelé pour reprendre les livraisons et promet un virement. Ne rien livrer sans l'accord de la comptabilité.
