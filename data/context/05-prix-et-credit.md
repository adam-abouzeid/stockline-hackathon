# Prix et crédit

## Prix de vente

- Tarif annuel revu au 1er janvier (vins, spiritueux, softs) ; crus classés au tarif de septembre, après la campagne des primeurs.
- Fûts consignés 30 € HT, casiers verre 6 € HT : facturés si non rendus sous 30 jours.
- Minimum de commande 150 € HT, sinon 18 € de frais de livraison ; franco pour les contrats annuels.
- Allocations de crus classés : attribuées par Claire selon l'historique d'achat du client.
- Remises : seuls les commerciaux et Claire ; l'ADV ne peut rien accorder.

Ordre de résolution : prix négocié client > règle de prix (client, puis groupe) > prix liste.

## Groupes de clients

- **Bars** (`bars`) : Bars, pubs et bars à vins : pression, softs, spiritueux, vins au verre.
- **Brasseries** (`brasseries`) : Brasseries et restaurants traditionnels : gros volumes, bag-in-box, eaux.
- **Gastronomie** (`gastro`) : Tables gastronomiques : grands crus, millésimes exacts, sommeliers.
- **Hôtellerie** (`hotellerie`) : Hôtels : bar, petit-déjeuner, économat, facture au mois.
- **Cavistes** (`cavistes`) : Revendeurs : sensibles au prix de vente conseillé, forts en décembre.
- **Saisonniers du Bassin** (`saisonniers`) : Paillotes et cabanes : avril à septembre, glaçons, rosé.
- **Événementiel** (`evenementiel`) : Traiteurs et salles : volumes irréguliers, reprise des invendus.
- **Détaillants** (`detaillants`) : Supérettes de proximité.
- **Grands comptes** (`grands-comptes`) : Contrats annuels avec prix fixés au 1er janvier.
- **À surveiller** (`a-surveiller`) : Retards de paiement, litiges ou compte bloqué : vérifier l'encours avant toute commande.
- **Clients perdus** (`perdus`) : Plus de commande depuis plusieurs mois (partis à la concurrence ou fermés) : à reconquérir.

## Règles de prix

- `prl_0001` Bars : −4 % sur la pression, du 01/01/2025 — Contrat pression avec tireuse prêtée.
- `prl_0002` Cavistes : −6 % sur les grands crus, du 01/09/2024 — Pour tenir le prix de vente conseillé.
- `prl_0003` Gastronomie : −3 % sur les rouges, du 01/01/2025
- `prl_0004` Saisonniers : −5 % sur les rosés dès 12 bouteilles, du 01/04/2025
- `prl_0005` Volume : Bordeaux supérieur −5 % dès 60 bouteilles, du 01/01/2024
- `prl_0006` Fêtes 2026 : champagne brut −7 % dès 24 bouteilles, du 01/12/2026 au 31/12/2026 — Opération fin d'année validée avec Vauthier-Roussel.
- `prl_0007` Beaujolais nouveau 2026 : prix net 6,50 € dès 24 bouteilles, du 10/11/2026 au 30/11/2026
- `prl_0008` Événementiel : −8 % sur le crémant, du 01/01/2025

## Crédit et relances

- Plafond d'encours par client (TTC) ; au-delà, la commande passe en validation chez Martine.
- Relance à J+5 par mail, J+15 par téléphone, J+30 courrier ; blocage à J+45 ou au premier prélèvement rejeté deux fois.
- Déblocage : règlement d'au moins 50 % de l'échu et échéancier validé par Claire.
- Saisonniers du Bassin : tolérance jusqu'à fin octobre sur les factures de juillet-août.

## Clients à surveiller (au 24/11)

- Le Zinc de la Victoire (cli_0007) : mauvais payeur, compte à risque, 11 facture échues pour 15 843,53 € TTC — **bloqué**.
- Le Bistrot du Marché des Capucins (cli_0008) : mauvais payeur, compte à risque, 2 facture échues pour 33 472,85 € TTC — **bloqué**.
- Le Petit Chai (cli_0013) : paie en retard (3 à 6 semaines), mais finit par payer, 3 facture échues pour 4 278,62 € TTC.
- Le Bar de Bordeaux (Saint-Michel) (cli_0016) : paie en retard (3 à 6 semaines), mais finit par payer, 3 facture échues pour 7 076,63 € TTC.
- Les Salons de Pey-Berland (cli_0024) : paie en retard (3 à 6 semaines), mais finit par payer, 3 facture échues pour 15 183,79 € TTC.
- Brasserie Philippe (cli_0025) : paie en retard (3 à 6 semaines), mais finit par payer, 2 facture échues pour 3 880,49 € TTC.
- Le Cabanon d'Andernos-les-Bains (cli_0026) : paie en retard (3 à 6 semaines), mais finit par payer, 2 facture échues pour 5 558,50 € TTC.
- Les Terrasses de Pey-Berland (cli_0028) : paie en retard (3 à 6 semaines), mais finit par payer.
- Château David (réceptions) (cli_0032) : paie à l'heure mais déduit ce qu'il conteste, 2 facture échues pour 4 422,03 € TTC.
- Bar des Le Gall (cli_0034) : paie en retard (3 à 6 semaines), mais finit par payer, 7 facture échues pour 4 567,92 € TTC.
- Le Comptoir Gourmand (cli_0038) : paie en retard (3 à 6 semaines), mais finit par payer.
- La Petite Cave de Vincent (cli_0039) : paie en retard (3 à 6 semaines), mais finit par payer, 1 facture échue pour 4 354,12 € TTC.
- Dufour Réceptions (cli_0040) : mauvais payeur, compte à risque, 2 facture échues pour 13 388,70 € TTC — **bloqué**.
- Hôtel des Vignes (cli_0044) : paie en retard (3 à 6 semaines), mais finit par payer, 1 facture échue pour 18 832,02 € TTC.
- La Buvette du Quai (cli_0046) : paie en retard (3 à 6 semaines), mais finit par payer.
