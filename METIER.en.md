# The food wholesale trade — reference

> English translation of [METIER.md](METIER.md). The French original is the reference. French trade terms are kept
> in *italics* where callers will use them, with an English gloss.

This document explains in detail how a food wholesaler works and how each concept shows up in the kit's ERP. Read
it to choose your problem and so that your agent talks and acts like a professional. The general brief is in
[BRIEF.en.md](BRIEF.en.md).

## How to read this document

- **For humans**: read "The trade on one page", "The chain", "The players" and "Where voice changes the game". The
  rest serves as a reference during the 24 hours.
- **For coding agents** (Claude Code, Cursor…): each domain ends with an **In the ERP** block that gives the exact
  names in backticks: entities and fields (`Order.status`), routes (`/api/context/for`), agent tools (`get_price`),
  interface pages (**Commandes**). The **Rule** lines are explicit business rules. When a rule is only written in
  the context and *not* enforced by the backend, that is stated.
- **The examples** come from the **Marée de Rungis** pack ("the pack" below). Your team receives its own company's
  pack in `./data`, with the same structure (`seed/` and `context/`). Marée de Rungis is a fictional seafood
  wholesaler based at the Rungis MIN (national wholesale market): 66 products, 100 clients, about €1.2M excl. VAT
  of sales per month, an average basket of about €920 excl. VAT. Everything is fictional. The pack's "today" is
  `meta.today` = Tuesday 24 November 2026, and the reference time is 4:30 a.m.: the trucks haven't left yet.
- The document covers all of food wholesale (seafood, fruit and vegetables, meat, dairy, groceries, beverages,
  frozen). There are 24 fictional companies, one per team, and yours may belong to another family: the principles
  are the same, only the products, units and rhythms change.

---

## The trade on one page

A food wholesaler buys in bulk, stores for a short time, and resells in small quantities to professionals:
restaurants, shops, canteens, hotels. It doesn't sell to individuals. It's also called a "distributor" or an "RHD
wholesaler" (*restauration hors domicile*, out-of-home catering / food service).

What it really sells is not just product. It is:

- **the right product**, chosen from dozens of suppliers, at the right size grade, at the right quality;
- **at the right time**, delivered before service, often before 7 a.m.;
- **in small quantities**, whereas the supplier sells by the pallet or the lot;
- **on credit**, paid 30 days later;
- **with advice**: "turbot is outrageously expensive this week, take John Dory".

Three figures sum up the difficulty:

| Constraint | Order of magnitude | Consequence |
|---|---|---|
| Gross margin | 15 to 35% of the selling price | Little room for error. The final net margin is often only a few percent. |
| Shelf life of fresh products | 3 to 5 days for fish, a few days to a few weeks for fruit and vegetables and meat | Everything not sold in time is thrown away. |
| Client ordering lead time | a few hours, often at night | You have to buy before knowing what you'll sell. |

The wholesaler makes a living in a fragile balance: buying enough never to say "I'm out of it", without buying what
will end up in the bin, and getting paid by clients who pay late.

### Product families

Each wholesaler specializes in one or two families. The rules change a lot from one to the other.

| Family | Examples | Selling unit | Shelf life | What drives the price | Main hazard |
|---|---|---|---|---|---|
| **Seafood** (*marée*) | sea bass, sole, oysters, langoustines, mussels | kg, dozen, piece | 3 to 5 days; live shellfish | the day's auction, species, size grade, wild or farmed | weather: no fishing in a storm |
| **Fruit and vegetables** | lemons, salads, potatoes, herbs | parcel, crate, kg, bunch | from 2 days (herbs, strawberries) to several weeks (potatoes) | season, origin, class (Extra, I, II), size grade | weather, frost, harvest; ripeness |
| **Meat** | beef, veal, poultry, lamb | kg, piece, carcass or cut | a few days to a few weeks vacuum-packed | breed, origin, class, cut, aging | market prices, health crises |
| **Dairy** (*crèmerie*) | butter, cream, cheeses, eggs | kg, liter, piece, tray | from a few days (crème fraîche) to months (aged cheeses) | PDO, aging, brand | milk seasons, aging |
| **Groceries** (*épicerie*) | oil, canned goods, salt, flour | carton, can, piece | months (best-before) | brand, annual contract | little: long stock, stable prices |
| **Beverages** | wine, beer, sodas, waters | carton, keg, bottle | long | brand, contract, excise duty on alcohol | deposits (kegs, glass), season (summer) |
| **Frozen** | breaded fish, fries, frozen vegetables | carton, kg | months at −18 °C | contract, volume | cold-chain break |

The Marée de Rungis pack is a **seafood** wholesaler with a little fruit and vegetables, dairy and groceries on the
side: that's common, the chef wants to receive everything in the same truck.

---

## The chain: from boat to plate

```
  UPSTREAM (produce)          FIRST SALE                       WHOLESALE               CLIENTS
  ──────────────────          ──────────                       ─────────               ───────
  fishermen ─────────▶ fish auction (criée) ─▶ fish wholesaler ┐
  oyster farmers, mussel farmers ─────────────────────────────┤
  market gardeners, fruit growers ─▶ cooperative / shipper ───┤
  livestock farmers ─▶ slaughterhouse ─▶ cutting plant ───────┼─▶ WHOLESALER ─▶ restaurants, brasseries,
  dairies, cheesemakers, affineurs ───────────────────────────┤   (often         fishmongers, greengrocers,
  manufacturers (groceries, frozen, beverages) ───────────────┤    at a MIN)     canteens, care homes, hotels,
  importers (Norwegian salmon, citrus, tuna…) ────────────────┘                  caterers, supermarkets
```

### The links, one by one

- **Fishermen.** They land their catch at the port. Small coastal fishing goes out for the day; bigger boats leave
  for several days. In heavy weather, boats stay in port: nothing arrives anymore.
- **Fish auction** (*criée*, or *halle à marée*). The port's market where the catch is sold at auction, often on
  screen, very early in the morning. The buyers are registered professionals, mostly fish wholesalers
  (*mareyeurs*). The price changes there every day. Examples in the pack: the Boulogne-sur-Mer, Lorient and Le
  Guilvinec auctions.
- **Fish wholesaler** (*mareyeur*). The first buyer of the fish. He buys at the auction, sorts, washes, ices,
  sometimes fillets, and ships the same day to wholesalers. He's the one the seafood wholesaler calls. Examples:
  Boulogne Marée Mareyage (`sup_0001`), Mareyage de Keroman (`sup_0002`), Bigouden Marée (`sup_0003`).
- **Direct producers.** Oyster farmers, mussel farmers, market gardeners, cheesemakers. They sell themselves, often
  with minimums and longer lead times. Example: Huîtres Joubert (`sup_0004`), at D+2.
- **Cooperatives and shippers.** They pool the production of many farmers, sort it, grade it and pack it. Common in
  fruit and vegetables and in milk.
- **Slaughterhouses and cutting plants.** For meat: the animal becomes a carcass, then quarters, then cuts ready to
  be cut further or vacuum-packed portions.
- **Importers.** They bring in what France doesn't produce enough of or out of season: salmon from Norway and
  Scotland, tuna from the Indian Ocean, citrus, exotic fruit. Often based at the wholesale markets. Example:
  Highland & Fjord Seafood (`sup_0006`), at Rungis, payment at 45 days.
- **Manufacturers.** Frozen, groceries, beverages. Prices negotiated for the year, long stock, planned deliveries.
  Example: Océane Surgelés (`sup_0007`), delivery D+2, free shipping from €1,500.
- **MIN (*marché d'intérêt national*, national wholesale market).** Large public wholesale markets where
  wholesalers, producers and buyers are concentrated. **Rungis**, south of Paris, is the largest: it is organized
  in pavilions (seafood, meat, fruit and vegetables, dairy, etc.) and lives at night. There are also regional MINs
  (Lyon, Marseille, Toulouse, Nantes, Lille, Bordeaux…). Being at a MIN means having dozens of suppliers a few steps
  away: you can walk over to the neighbor to fetch a case of lemons (Primeurs Dufresne, `sup_0008`, two aisles
  down). Many wholesalers are not at a MIN and have their own warehouse in a business park.
- **The wholesaler.** Buys from all these links and resells to hundreds of professionals.
- **The clients.** Restaurants, food shops, public catering, hotels, caterers, sometimes supermarkets. Details
  below.

There are also **competitors** the client compares the wholesaler with: the other wholesalers at the same market,
the large national food-service distributors (huge catalog, tight prices, less flexibility), cash-and-carry
wholesalers (the chef does his own shopping), and producers who sell direct.

### What the wholesaler brings

| Value | What it means in practice | Example |
|---|---|---|
| **Assortment** | A single contact for 60 to several thousand items, from dozens of suppliers | The chef receives sea bass, oysters, lemons and butter in the same truck. |
| **Breaking bulk** | Buys by the lot or the pallet, resells by the kilo | The fish wholesaler sells 50 kg of sea bass; the bistro wants 3. |
| **Selection and expertise** | Knows quality, size grades, seasons, reliable suppliers | "Don't take turbot this week, nothing was landed." |
| **Night-time availability** | Answers between 10 p.m. and 6 a.m., when the chef finishes service or the fishmonger opens | Ostréa orders between 1 and 3 a.m. |
| **Logistics and cold** | Refrigerated trucks, delivery runs, early-morning slots | Delivery before 7 a.m. at dock no. 2 of the Vitry central kitchen. |
| **Credit** | The client pays at 15, 30 or 45 days; the wholesaler finances the gap | Le Comptoir de Marie has about €5,300 outstanding against a €6,500 limit. |
| **Food safety** | Cold chain, lot traceability, fast withdrawal in case of an alert | It knows which clients received lot no. X. |
| **Getting clients out of a jam** | Finds a solution when the product is missing | Offering hake when cod prices have soared. |

**Rule.** The client doesn't only compare prices. They compare reliability (delivered on time, the right product),
quality, flexibility (ordering late, small quantities) and credit. An agent that only talks about price misses the
point.

---

## The players

### Suppliers and how buying works

| Type | What it sells | Typical lead time | Price | What to know |
|---|---|---|---|---|
| **Auction fish wholesaler** | fresh fish of the day | D+1 (night truck) | changes every day with the auction | depends on the weather; order cut-off time (often in the morning, before the auction) |
| **Direct producer** (oyster farmer, market gardener, cheesemaker) | its own production | D+1 to D+3 | fairly stable, not very negotiable | small volumes, minimum order, closely watched quality |
| **Cooperative, shipper** | pooled and graded production | D+1 to D+2 | seasonal campaign price, varies with the season | large volumes, standardized classes |
| **Importer** | foreign products, out of season | D+1 (stock on site) | tied to world prices and exchange rates | often longer payment (45 days) |
| **Manufacturer** (frozen, groceries, beverages) | processed products | D+2 to D+5, fixed days | annual contract | free shipping threshold, planned ordering |
| **Fellow wholesaler** | emergency supply | immediate | more expensive | you buy from them when you're out of stock |

**How a buyer buys, in practice.** The buyer (Franck Le Bihan in the pack) works at night and early in the morning.
Every day:

1. He looks at what was sold, what is already ordered by clients, what is left in stock and what expires soon.
2. He checks the *mercuriales*: the day's price lists that suppliers send (by email, message, phone). For the same
   product, he often has two or three possible suppliers.
3. He **calls** several suppliers, compares price and quality, and **negotiates**: "Si je te prends 50 kilos, je
   ne veux pas dépasser 22,80." ("If I take 50 kilos from you, I don't want to go over 22.80.") The arguments are
   volume, loyalty, the competitor's price, and buying several species together.
4. He **reserves** rare lots: "Garde-moi les homards bleus de vendredi." ("Keep Friday's blue lobsters for me.") On
   shortage days, a supplier serves its loyal, good-paying clients first.
5. He places the order, respecting the **minimum order** and the *franco* (the amount above which transport is
   free).
6. He **receives** the goods the following night: he checks quantity, temperature, quality and size grade.
   Anything missing or unsuitable becomes a supplier dispute.

What makes a supplier good or bad: **reliability** (delivers what was promised), **consistent quality**, **price
flexibility**, **punctuality** and the relationship. Each supplier has its personality: Loïc Tanguy (Bigouden
Marée) never confirms before seeing the boats; Gwenaël Le Corre (Keroman) negotiates above 50 kg per species and
closes orders at 9 a.m.

**Rule.** Paying your suppliers on time is a buying argument: on shortage days, the supplier serves clients who pay
well first.

### Transport

- **Own trucks.** Most wholesalers have their own refrigerated trucks and drivers. Each truck does a **delivery run**
  (*tournée*): one zone, certain days, a departure time, a sequence of stops.
- **Carriers and rental companies.** For peaks (holidays, busy Saturdays) or distant zones, you rent a truck with a
  driver, or hand the parcels to a refrigerated carrier. You then have to **book**: volume (m³), load (kg),
  temperature ("positive cold" 0/+4 °C or negative), departure time, dock, list of stops, price. Example in the
  pack: booking a 12 m³ truck from a rental company for Saturday 28/11.
- **The client who comes in person.** Some come to the dock to pick up their order (Le Relais de Rungis).
- **Upstream transport.** Suppliers deliver to the wholesaler with their night trucks, or through specialized
  carriers (fish from Brittany arrives at Rungis at night).

Transport constraints: **the cold chain** (never a temperature break), **time slots** (a restaurant doesn't take
deliveries during service, a canteen wants everything before 7 a.m.), **capacity** (truck weight and volume),
**stop order** (you don't cross Paris twice), and **returns** (refused goods, deposits, empty crates).

### Clients

| Type | Examples from the pack | How they order | When | What matters most |
|---|---|---|---|---|
| **Fine-dining restaurant** | La Table d'Aurélien, Maison Clément | The chef calls or sends a WhatsApp, product by product, demanding on size grade and origin | in the evening after service or at night | quality, accuracy, no substitutions |
| **Bistro, traditional restaurant** | Le Bistrot du Port, Le Comptoir de Marie | Phone, "comme d'habitude" ("the usual"), asks the price | the day before or at night | price, consistency, advice |
| **Brasserie** | Brasserie Le Mazarin | Email from the manager + calls from the oyster shucker; large regular volumes, contract | the day before, during the day | volume-negotiated price, reliability, service |
| **Fishmonger, greengrocer** (retail) | Poissonnerie Lemoine, Marée Bleue | Phone at night, compares every day, buys what looks good and is cheap | at night for the same morning | price, freshness, presentation, opportunities |
| **Institutional catering** (canteen, central kitchen, care home, staff restaurant) | Cuisine centrale de Vitry, EHPAD Les Tilleuls | Firm order by email, 2 to 3 days ahead, according to fixed menus | on fixed days, well in advance | compliance with the contract, fixed prices, food safety, punctuality |
| **Hotel** | Hôtel Le Marceau | A stores department that centralizes, internal purchase order number, chef's extras to be approved | the day before, during the day | procedure, compliant invoice, consistency |
| **Caterer** | Maison Berthier | Per event, large one-off volumes, several days ahead | according to the event calendar | volume guaranteed on the date, quoted price |
| **Supermarket** (*GMS*) | Frais d'Ici Créteil | Portal or EDI, before a cut-off time | the day before, before 2 p.m. | regulatory labeling, compliance, price |
| **Export** | — (not in the pack) | Grouped orders, long transport | planned | documents, certificates, packaging |

**They compare.** A professional client almost always has two or three wholesalers. They call them the same
evening, compare the price of sea bass, last week's quality, and split their orders. There are two profiles:

- **The loyal one**: one main wholesaler, for trust, credit and the relationship with their sales rep. They leave
  after an accumulation of small mistakes, rarely over a few cents.
- **The opportunist**: buys at the best price of the day. Fishmongers and greengrocers often are: their margin
  depends on their purchase price.

Who prioritizes what (★★★ = decisive criterion):

| Client type | Price | Quality | Service (time, flexibility) | Payment terms | Personal relationship |
|---|---|---|---|---|---|
| Fine dining | ★ | ★★★ | ★★★ | ★ | ★★★ |
| Bistro | ★★ | ★★ | ★★ | ★★ | ★★ |
| Brasserie | ★★★ | ★★ | ★★★ | ★★ | ★★ |
| Fishmonger, greengrocer | ★★★ | ★★★ | ★★ | ★★ | ★ |
| Public institution | ★★★ (set by the contract) | ★★ (compliance) | ★★★ (punctuality) | ★ (pays slowly but surely) | ★ |
| Hotel | ★★ | ★★★ | ★★ | ★★ | ★ |
| Caterer | ★★ | ★★ | ★★★ (volume on the date) | ★★ | ★★ |
| Supermarket | ★★★ | ★★ | ★★ (compliance, labeling) | ★★ | ★ |

**Public institutions, a world apart.** A public canteen buys through a **public contract** (*marché public*): a
tender, a specification, a **price schedule** (*bordereau de prix*) fixed for a year or more, by lots ("seafood",
"fruit and vegetables"). The wholesaler wins or loses the whole contract. After that, no negotiation on the phone:
"le bordereau, c'est le bordereau" ("the schedule is the schedule"). Any price deviation or unplanned substitution is
a problem. Payment goes through the public treasury, often slowly, and the invoice is filed on the public invoicing
platform (Chorus Pro). In public institutional catering, the law also requires a share of sustainable, quality
products (including organic): it's a criterion for choosing suppliers. Care homes and canteens have strict
requirements: boneless fillets, no shellfish, adapted textures.

### Internal roles: who does what, who calls whom

| Role | In the pack | What they do | Hours |
|---|---|---|---|
| **Manager, management** | Bruno Ménard | Approves big disputes, account unblocking, investments, contracts | daytime |
| **Sales reps** | Sophie, Karim, Julien, Nadia | Client portfolio, order taking, prices and discounts, visits, prospecting | staggered, often early |
| **Night switchboard, telesales** | Lucas Petit | Takes orders from 8 p.m. to 6 a.m., doesn't negotiate | night |
| **Buyer** | Franck Le Bihan | Buys every night, follows prices, negotiates, receives | night and morning |
| **Pickers** | (unnamed) | Take each order, weigh, pack, label | 2 – 5 a.m. |
| **Delivery drivers** | Mickaël, Abdel, Sébastien, Thierry, Patrick, Romain | Deliver, sometimes collect payment, bring back returns and remarks | 5 – 9 a.m. |
| **Accounting, collections** | Hélène Garnier | Invoices, credit notes, receipts, reminders, unpaid invoices | daytime |
| **Quality** | (often the manager in an SME) | HACCP plan, temperatures, traceability, recalls | daytime |

Who calls whom:

| Who | Calls | For |
|---|---|---|
| Client | sales rep or night switchboard | ordering, asking a price, changing, complaining, asking the delivery time |
| Sales rep | client | offering an arrival, chasing a silent client, announcing a stock-out, negotiating a contract |
| Buyer | suppliers | price lists, negotiation, reserving lots, quality complaints |
| Supplier | buyer | announcing a shortage, a price rise, a balance delivery, chasing a payment |
| Accounting | client, supplier | chasing an unpaid invoice, settling an invoice dispute |
| Driver | office, client | delay, client absent, goods refused |
| Colleague | colleague | "il nous reste combien de Saint-Jacques ?" ("how many scallops do we have left?"), "tu peux rappeler Marie ?" ("can you call Marie back?") |
| Manager | carrier, bank, big clients | booking a truck, negotiating a contract, unblocking an account |

---

## Economics and tensions of the trade

**Thin margins.** The wholesaler's gross margin is generally 15 to 35% of the selling price (in the pack: between 15
and 35% for each product, from `Product.cost` to `Product.price`). Once the trucks, drivers, cold storage, rent and
unpaid invoices are paid for, little is left. Every mistake costs money directly.

**Working capital.** The wholesaler pays its suppliers at 21, 30 or 45 days, and its clients pay it at 30 or 45
days, sometimes 60 in practice. In between, it advances the money. With €1.2M of sales per month, a fifteen-day gap
means about €600k to finance permanently. A client who pays late costs cash; a client who doesn't pay costs the
whole margin of dozens of other orders.

**Perishability.** A simple example: you buy for €100, resell for €133 (a 25% margin on the selling price, i.e. €33
gross margin). If 3% of what you buy ends up in the bin, you lose €3 out of 33: nearly 10% of the gross margin
disappears. For fresh fish, which keeps 3 or 4 days, every day counts.

**Having the right product at the right time.** You have to buy *before* you know. Clients order the day before or
the same night, but the buyer places orders the previous night for the next. Too little: stock-out, disappointed
client, client who leaves. Too much: unsold goods, forced promotion, loss. The trade consists in forecasting from
history ("on Tuesdays, Marée Bleue orders big"), the calendar (holidays, school vacations), the weather, the orders
already received and clients' promises.

**Price volatility.** Fresh purchase prices move every day (in the pack: ±10% around the reference cost). The selling
price, however, must stay readable for the client. A sudden rise is handled through advice ("take hake this week")
rather than a price rise announced on the phone.

**Variable quality.** Two lots of the same product aren't equal: size, freshness, fat, color, presentation. The
fine-dining chef refuses what a bistro will accept. The wholesaler must steer each lot to the right client.

**Moving stock.** A lot approaching its date must go: it's called "à pousser" ("to push"). The levers: offer it to
clients who usually take it, make a price, offer it to clients open to promotions (fishmongers, brasseries),
process it (fillets, portions), or downgrade it.

**Substitution.** When a product is missing, you offer an equivalent: another size grade, another origin, farmed
instead of wild, frozen instead of fresh. It's a service if the client agrees, a fault if they don't.

**Credit risk.** Each client has a **credit limit** (maximum outstanding balance allowed). You have to watch for
delays, send reminders, sometimes **block** a client: no more deliveries until they've paid. Blocking too early
loses a client; too late, money.

**Competition.** The client compares every day. The relationship (the sales rep who knows the chef's menu, who calls
back at the right time, who remembers the complaint) is often what makes the difference.

---

## A 24-hour day

The schedule of a seafood wholesaler at a MIN, as in the pack. A fruit-and-vegetable or meat wholesaler has a
similar rhythm, a bit later; a grocery or beverage wholesaler works mostly during the day.

| Time | What happens | Who | In the pack |
|---|---|---|---|
| Day before, 4 – 9 a.m. | Auctions in the ports; fish wholesalers buy; price lists sent | fish wholesalers, buyer | the day's supplier prices (`SupplierPrice.updatedAt`) |
| Day before, 9 a.m. – 2 p.m. | The buyer finishes negotiating for the next night; sales reps on the phone; hotels and institutions send their orders | buyer, sales reps | orders `createdBy` = sales rep |
| Day before, 2 – 6 p.m. | Orders by email from brasseries, from the supermarket portal (before 2 p.m.); invoicing, reminders | sales reps, accounting | `Order.source` = `email`, `web` |
| Day before, 6 p.m. – midnight | Chefs order after service (phone, WhatsApp) | night switchboard | `createdBy: "lucas"`, `source: "whatsapp"` |
| 0 – 2 a.m. | Oyster bars, late restaurants; supplier trucks on the road | night switchboard | `draft` orders to approve |
| 2 – 3 a.m. | Receiving supplier trucks: inspection, one lot per line | receiving clerk, buyer | `Lot`, `receipt` movements |
| 3 a.m. | Night inventory: discard what is past its date, downgrade | pickers | `waste`, `adjustment` movements |
| 2 – 4:30 a.m. | Fishmongers and bistros order for the same morning; picking, weighing, labeling | switchboard, pickers | `preparedQty`, status `prepared` |
| 3:40 – 4 a.m. | The buyer sends supplier orders for the next night (or D+2, D+3) | buyer | `PurchaseOrder.status` = `sent` |
| 4:30 a.m. | Cut-off time to be delivered the same morning | — | `meta.today` at 4:30 a.m. |
| 5 – 6 a.m. | Delivery runs depart | drivers | the day's `RouteRun` |
| 5:30 – 9 a.m. | Deliveries; "where's the truck?" calls; refusals and returns at unloading | drivers, office | status `delivered`, `sale` movements |
| 9 a.m. – noon | Trucks, returns and crates come back; morning complaints; the day's auctions | drivers, sales reps | `ClientEvent` of type `complaint` |
| noon – 6 p.m. | Invoicing, receipts, reminders, quotes, prospecting, preparing purchases | accounting, sales reps | `Invoice`, `Payment` |

On Sundays, nothing usually runs. On Mondays, some delivery runs don't run (in the pack, Paris Sud and
Hauts-de-Seine & Yvelines). On Christmas Eve and New Year's Eve, volumes explode and hours stretch.

---

## The trade's rules (hygiene, traceability, payment)

These rules are general and simplified. They are enough for an agent not to say anything stupid.

- **Cold chain.** Fresh goods stay in positive cold (around 0 to +4 °C; fish under ice, close to 0 °C). Frozen goods
  stay at −18 °C or below. A thawed product is not refrozen. Temperatures are checked at receiving, in the cold room
  and in the trucks.
- **HACCP.** Every food business applies a hygiene plan based on hazard analysis (HACCP): critical points,
  temperatures, cleaning, training. Establishments that handle products of animal origin generally have a
  **health approval** (the oval mark on labels).
- **Lot traceability.** Every professional must know from whom they received a product and to which professional
  they delivered it ("one step up, one step down"). So the wholesaler tracks each **lot**: supplier, date received,
  expiry date, clients delivered. In case of a health alert, it must be able to **withdraw** the lot and notify the
  clients concerned quickly.
- **DLC and DDM.** The **DLC** (*date limite de consommation*, use-by date, "à consommer jusqu'au") concerns very
  perishable products: after it, you no longer sell, you throw away. The **DDM** (*date de durabilité minimale*,
  best-before date, "à consommer de préférence avant") concerns stable products (groceries): after it, the product
  may lose quality but isn't dangerous.
- **Origin labeling.** For fish sold to consumers: commercial name and scientific name, production method (caught or
  farmed), catch area (FAO zone) or farming country, and type of fishing gear. That's why Frais d'Ici Créteil
  refuses any parcel without an FAO and fishing-gear label. For fruit and vegetables: country of origin and class.
  For beef: the origin is mandatory, including in restaurants.
- **Live shellfish.** Oysters, mussels, clams are sold alive, with a health label on every parcel.
- **VAT.** Foodstuffs are at 5.5% in France; alcoholic beverages at 20%. In the pack, the whole catalog is at 5.5%
  (`Product.vatRate` = 0.055).
- **Payment terms.** The law caps payment terms between businesses. For **perishable foodstuffs**, the cap is short:
  about 30 days after delivery (precisely, 30 days after the end of the ten-day period of delivery). Other purchases
  are capped higher. Any delay gives the right to penalties and a flat-rate collection fee. Public buyers have their
  own legal deadline, often exceeded in practice. In the pack, some clients have 45 days: that's a fictional choice,
  not to be taken as a legal model for fresh goods.
- **Prices and discounts.** Only authorized people (sales reps, management) grant a special price. A night
  switchboard or a voice agent doesn't negotiate: it notes and passes on.

---

## The trade's domains, one by one

Each block follows the same outline: **What it is**, **Vocabulary**, **How it works**, **The challenges**,
**In the ERP**.

### Clients

**What it is.** The portfolio: about a hundred very different professionals (see "Clients" above). Each has its
delivery days, its payment terms, its habits, its contacts and its history with the wholesaler.

**Vocabulary.**

- *Fiche client* (client profile): address, zone, delivery days, payment terms, limit, sales rep.
- *Commercial attitré* (assigned sales rep): the person who "holds" the client. Some clients only want to talk to
  them.
- *L'habituel*, *le panier habituel* (the usual, the usual basket): what the client almost always orders.
- *Encours*, *plafond de crédit*, *client bloqué* (outstanding, credit limit, blocked client): see Invoicing.
- *Prospect*: potential client, no order yet.
- *Client à risque*, *client qui décroche* (at-risk client, client drifting away): orders less, compares more,
  complains.

**How it works.** Each client has a rhythm: every day, three times a week, depending on the menus. They have strong
habits ("comme d'habitude" — "the usual", "le saumon de la dernière fois" — "the salmon from last time") and fixed
requirements: Sakana wants Label Rouge Scottish salmon and never Norwegian, EHPAD Les Tilleuls wants boneless
fillets, Racines & Marée is closed on Mondays and Tuesdays. They often have several contacts: the chef chooses the
products, the manager approves the prices, the accountant pays. At Hôtel Le Marceau, everything goes through the
stores department with an internal purchase order number. Maison Clément only wants to be called back by Karim, and
never after 5:30 a.m.

**The challenges.**

- The client never gives their identifier. They say "c'est Marc du Bistrot" ("it's Marc from the Bistrot"), "c'est
  Yann", or nothing at all. You have to recognize them by name, number, voice, context.
- You have to remember everything: last week's complaint, the late payment, the sous-chef's first name, the August
  closure. The best sales rep does it from memory; the night switchboard can't.
- A badly treated client goes to the competitor across the aisle, often without saying anything: they just order
  less.

**In the ERP.**

- `Client` entity: `code`, `name`, `type` (`restaurant` | `brasserie` | `fishmonger` | `canteen` |
  `supermarket` | `caterer` | `hotel`), `contacts[]` (`name`, `role`, `phone`, `email`), `address`, `city`,
  `zone`, `deliveryDays` (`mon`…`sun`), `paymentTermsDays`, `creditLimit`, `status` (`active` | `blocked` |
  `prospect`), `salesRep`, `preferences` (free-text summary), `notes[]` (`at`, `author`, `text`), `tags` (client
  groups: `gastro`, `brasseries`, `collectivites`, `marche-public`, `a-surveiller`…).
- Usual basket: `GET /api/clients/{id}/usual`, computed over the orders of the last 60 days (products present in at
  least 25% of orders, with `avgQty`, `lastQty`, `frequency`).
- Full profile: `GET /api/clients/{id}` (negotiated prices, recent orders, open invoices, payments, usual basket,
  history). Sales rep note: `POST /api/clients/{id}/notes`.
- Memory: context table (`ContextEntry`, `entityType: "client"`, `entityId: "cli_…"`), with entries per client
  ("Comment leur parler" — "How to talk to them", "Ce qui les agace" — "What annoys them", open cases).
  `GET /api/context/for?entityType=client&id=cli_0001`. Readable persona profiles in `./data/context/clients/`.
- Agent tools: `search` ("bistrot du port" → `cli_0007`), `get_client` (profile, usual basket, notes, open issues,
  last 5 events), `get_context`, `save_context` (remember a durable fact).
- Pages: **Clients**, client detail (Contexte tab, "Ce que l'agent sait" — "What the agent knows" block),
  **Contexte**, **Groupes**.
- **Rule.** Before answering a client: identify them (`search`), load their profile (`get_client`) and their context
  (`get_context`). Check `status`: `blocked` or `prospect` change the whole conversation.

### Order taking and sales

**What it is.** The heart of the business: turning a call, an email, a WhatsApp or a voice message into a correct
order, delivered to the right place on the right day. In the pack, over twelve months, 61% of orders come by phone,
24% by email, 9% by WhatsApp, 5% through the web portal and 2% are entered at the dock.

**Vocabulary.**

- *Pré-commande*, *brouillon* (pre-order, draft): an order entered but not yet confirmed by the client.
- *Ligne de commande* (order line): one product, one quantity, one price.
- *Quantité commandée* (ordered quantity) and *quantité préparée* (prepared quantity, the actual weight).
- *Heure limite*, *cut-off*: after it, the order goes to the next delivery day.
- *Rupture* (stock-out): no more stock. *Livraison partielle* (partial delivery): part is delivered.
- *Substitution*: one product instead of another, with the client's agreement.
- *Relecture*, *récap* (read-back, recap): reading the order back to the client before hanging up.
- *Bon de livraison (BL)* (delivery note): the document that accompanies the goods.
- *Dépannage* (emergency help): an urgent order outside the usual rules.

**How it works.**

1. The client calls, often at night, and dictates in a jumble: "Mets-moi 5 kilos de bar, 2 caisses de moules et des
   huîtres comme d'habitude." ("Put me down for 5 kilos of sea bass, 2 cases of mussels and oysters as usual.")
2. The seller identifies the products ("le loup" = sea bass), checks stock, gives prices if asked, offers an
   alternative if a product is missing.
3. He keeps **a single** order open and fills it in during the call: the client often adds an item at the end.
4. He **reads it back**: "Je récapitule pour demain mercredi : 6 kilos de sole 500-600, 3 kilos de noix de
   Saint-Jacques, 2 kilos de beurre demi-sel. Livraison par la tournée Paris Ouest, vers 6 h. C'est bon pour vous ?"
   ("Let me recap for tomorrow, Wednesday: 6 kilos of 500-600 sole, 3 kilos of scallop meat, 2 kilos of lightly
   salted butter. Delivery on the Paris Ouest run, around 6 a.m. Is that right for you?")
5. The client says yes: the order is **confirmed**. It then moves to picking, delivery, then invoicing.

**The challenges.**

- Names are fuzzy ("des n° 3" = size-3 cupped oysters, "des noix" = scallop meat, "du lieu" = pollack or saithe?).
  You have to clear up the doubt without annoying the client.
- Units vary: kilos, pieces, dozens, parcels, cases, "un seau de crème" ("a bucket of cream", 5 liters), "une
  bourriche de 4 douzaines" ("a basket of 4 dozen").
- The client changes their mind, interrupts, talks with noise in the background, at 3 a.m.
- Everything arrives at the same time between 10 p.m. and 4:30 a.m. A mistake means a chef without fish for service.
- The delivery day isn't obvious: before or after the cut-off, delivery-run day or not, the client's closing days.

**In the ERP.**

- Entities `Order` (`number` "CMD-2026-000123", `clientId`, `status`, `source`, `deliveryDate`, `routeRunId`,
  `totalHt`, `note`, `createdBy`, `confirmedAt`, `deliveredAt`, `invoiceId`) and `OrderLine` (`productId`, `qty`,
  `unitPrice`, `preparedQty`, `note`, `substituteFor`).
- `Order.status`: `draft` → `confirmed` → `prepared` → `delivered` → `invoiced`, or `cancelled` from `draft`,
  `confirmed` or `prepared`. A forbidden transition returns a 409 `invalid_transition` error.
- `Order.source`: `phone` | `voice_agent` | `email` | `whatsapp` | `manual` | `web`.
- Routes: `POST /api/orders`, `POST /api/orders/{id}/lines`, `PATCH /api/orders/{id}/lines/{lineId}`,
  `DELETE /api/orders/{id}/lines/{lineId}`, `PATCH /api/orders/{id}` (date, note), `POST /api/orders/{id}/confirm`,
  `/prepare`, `/deliver`, `/invoice`, `/cancel`.
- Agent tools: `create_draft_order`, `add_order_line`, `confirm_order`, `get_order`. There is no tool to modify or
  delete a line, change the date or cancel: the routes exist, the tools are yet to be written.
- Alerts: every in-progress order returns `warnings[]` with a `code`: `client_blocked`, `credit_limit`, `no_route`
  (no delivery run that day for the zone), `insufficient_stock`, `expiring_soon` (the first lot taken out expires no
  later than the day after delivery), `price_below_cost`. **These alerts never block**: the backend confirms anyway.
  It's up to the agent to react.
- Default date: without `deliveryDate`, the ERP takes the client's next delivery day *strictly after* `meta.today`.
  An order for the same morning must therefore give the date explicitly. The cut-off time (4:30 a.m. in the pack) is
  **not** enforced by the backend: it is written in `context/06-livraisons-zones.md`.
- Pages: **Commandes**, order detail (lines, alerts, delivery run, invoice), **Voix**, **Activité**.
- **Rule.** Only confirm (`confirm_order`) after an explicit "yes" from the client on the recap. Without clear
  confirmation, the order stays in `draft`.
- **Rule.** A single in-progress order per call: you add lines, you don't create a second one.
- **Rule.** A `prepared` order can no longer be modified, except the prepared quantity and the note (the backend
  enforces this). A `confirmed` order can still be modified.

### Products and catalog

**What it is.** From a few dozen to a few thousand items, organized by department. Departments are **specific to
each company** (`seed/categories.json`, `GET /api/categories` → `[{id, label}]`): look at yours.

**Vocabulary.**

- *Référence*, *article*, *SKU* (item code, e.g. `BAR-LIG-12`).
- *Calibre* (size grade): the size. Sea bass 1-2 kg, sole 500-600 g, langoustines 15/20 (15 to 20 pieces per kilo),
  oysters no. 3 (the smaller the number, the bigger the oyster).
- *Sauvage* or *de ligne* (wild or line-caught) versus *élevage* (farmed): very different price and image.
- *Origine* (origin): Brittany, Scotland, Norway, FAO zone.
- *Label*: Label Rouge, AOP/PDO (Mont-Saint-Michel bouchot mussels, Isigny butter), organic, MSC.
- *Unité de vente* (selling unit): kg, piece, dozen, parcel, liter. *Colisage* (pack size): how many units per
  parcel.
- *Alias*: the names clients use ("loup" for sea bass, "cab" for cod).
- *Saisonnier*, *hors saison*, *produit de fêtes* (seasonal, out of season, holiday product).
- *Produit à pousser* (product to push): a product to move quickly.

**How it works.** Each product has a list price, a reference cost, a unit, a shelf life, an origin, a size grade, a
main supplier and acceptable replacement products. The catalog changes with the seasons: sardines and spider crab
are inactive in November; the scallop season opens in October. A good seller also knows what isn't written
anywhere: which product looks good this week, which is expensive, which needs to be moved.

**The challenges.**

- The same product has ten names; two similar products have nothing in common for a chef (line-caught sea bass at
  €32.50/kg and farmed sea bass at €14.90/kg).
- The offer changes every day depending on the catch or the harvest.
- The agent must know the catalog better than the client, and know when to ask for clarification ("Lieu jaune ou
  lieu noir ?" — "Pollack or saithe?") rather than guess.

**In the ERP.**

- `Product` entity: `sku`, `name`, `aliases[]`, `category` (id of one of the company's categories, see
  `GET /api/categories`), `unit` (`kg` | `piece` | `box` | `dozen` | `liter`), `price` (list price € excl. VAT),
  `cost` (reference cost € excl. VAT), `vatRate`, `shelfLifeDays`, `origin`, `caliber`, `mainSupplierId`,
  `active`, `tags` (`premium`, `fetes`, `labels`, `best-sellers`, `saison`…).
- Routes: `GET /api/products?q=&category=&tag=`, `GET /api/products/{id}`, `GET /api/products/{id}/alternatives`.
- Fuzzy search: `GET /api/search?q=` (accents, typos, aliases, filler words ignored); `search` tool.
- Tools: `get_product_stock`, `find_alternatives` (same department, in stock, closest price), `get_context` with
  `entityType: "product"` or `"category"`.
- Full glossary with aliases, prices and use-by dates: `./data/context/03-glossaire-produits.md`.
- Pages: **Produits**, product detail, **Groupes**.
- **Rule.** `find_alternatives` only knows the department and the price. The "trade" replacement (wild turbot →
  farmed turbot, Label Rouge → Norway) and the client's refusals are in the context and the playbook: check them
  before offering.

### Prices

**What it is.** A product's price isn't the same for everyone, nor from one day to the next. A big client has
negotiated prices, a client group has discounts, a promotion lasts a week, a public contract fixes everything for a
year.

**Vocabulary.**

- *Prix catalogue*, *prix liste* (catalog price, list price): the base price.
- *Prix négocié*, *prix client* (negotiated price, client price): a price for one client and one product.
- *Remise* (discount, in %), *règle de prix* (price rule, for a client group or a department), *prix de volume*
  (volume price, "dès 50 kg" — "from 50 kg").
- *Marge* (margin): selling price minus cost. *Coefficient*: selling price divided by cost.
- *Cours du jour* (the day's rate): purchase price that varies with the auction.
- *Prix ferme* (firm price): guaranteed for a period. *Prix au bordereau* (schedule price): fixed by a public
  contract.
- *Cotation*, *devis* (quote): a price offered before the order.
- *Geste commercial* (goodwill gesture): a reduction granted to fix a problem.

**How it works.** A line's price is decided in this order:

1. A **negotiated price** for this client and this product: it always wins.
2. Otherwise, the most precise **price rule** that applies (for example "Gastro : −5 % sur les crustacés" — "Fine
   dining: −5% on crustaceans", "Volume : moules de bouchot −4 % dès 50 kg" — "Volume: bouchot mussels −4% from
   50 kg").
3. Otherwise, the **list price**.

The price is frozen on the line when it is created. Fresh purchase prices move every day, but selling prices stay
stable: you don't change the price of sea bass on the phone because the auction went up, you recommend another
species.

**The challenges.**

- Giving the right price the first time. A wrong price means lost margin or an angry client at invoice time.
- Defending the margin against a client who negotiates ("chez l'autre, c'est 2 € de moins" — "at the other guy's,
  it's €2 less").
- Knowing who can grant a discount. In the pack: only the sales reps; the night switchboard and the voice agent
  grant none. Le Zinc des Halles negotiates everything, but nothing is decided without Karim.
- Flagging a good deal: "à partir de 50 kilos, la moule passe à 4,70" ("from 50 kilos, mussels drop to 4.70").

**In the ERP.**

- `ClientPrice` (`clientId`, `productId`, `price`): `PUT` and `DELETE /api/clients/{id}/prices/{productId}`.
- `PriceRule`: `name`, `active`, `priority`, `clientScope` (`all` | `client` | `tag`), `productScope` (`all` |
  `product` | `tag` | `category`), `method` (`fixed` fixed price | `discount_pct` discount on the list price |
  `markup_pct` markup on cost), `minQty`, `validFrom`, `validTo`. Routes `/api/price-rules`.
- Resolution: `GET /api/prices/resolve?clientId=&productId=&qty=` returns `price`, `listPrice`, `source`,
  `explanation` in French and all the candidates. Grid: `GET /api/prices/grid?clientId=` or `?clientTag=`. The
  calculation lives in `apps/backend/app/services/pricing.py`, and nowhere else.
- Tool: `get_price` (also returns `betterPriceWithVolume` when a volume rule would give a better price).
- The order tools don't allow setting a price: the ERP resolves it. That's intentional.
- The pack's special agreements: `./data/context/05-prix-et-credit.md`.
- Page: **Prix** (clients × products matrix, rules, negotiated prices, margin simulator).
- **Rule.** Always go through `get_price` (or `/api/prices/resolve`) to give a price. Never compute a discount in the
  prompt.
- **Rule.** The voice agent grants no discount: it notes the request (`log_client_event` of type
  `price_negotiation`) and passes it on to the sales rep.

### Purchasing and suppliers

**What it is.** Buying every night what will be sold in the following days, from fish wholesalers, producers,
importers and manufacturers (see "Suppliers" above).

**Vocabulary.**

- *Commande d'achat*, *commande fournisseur*, *bon de commande* (purchase order, supplier order).
- *Mercuriale*: a supplier's price list of the day.
- *Délai* (lead time): D+1, D+2, D+3 (days between order and delivery).
- *Minimum de commande* (minimum order), *franco* (amount above which transport is free).
- *Arrivage*, *débarque* (arrivals, what the boats bring back), *apport* (supply).
- *Réception* (receipt), *réception partielle* (partial receipt), *complément* (the remainder, delivered later).
- *Couverture* (cover): how many days of sales the stock can sustain.
- *Référencement* (listing): bringing in a new supplier.

**How it works.** The buyer compares several suppliers' prices, calls to negotiate or reserve a lot, places the
order, then receives it. In the pack: fresh goods are ordered every night for the following night, with about two
days of cover; frozen goods on Monday, Wednesday or Thursday (D+2); dairy and groceries on Monday or Thursday
(D+3). The goods sometimes arrive in a different quantity or quality: Huîtres Joubert delivered short on the
spéciales no. 3, with the balance announced for Thursday.

**The challenges.**

- Buying enough to serve everyone, without buying what will end up in the bin.
- Comparing prices that change every day, between suppliers that aren't equally reliable.
- Reacting when the boats don't go out: the storm in Brittany brings wild turbot and 15/20 langoustines to zero, and
  a purchase order stays in draft until the supplier has confirmed.
- Respecting each supplier's minimums and cut-off times.

**In the ERP.**

- `Supplier`: `name`, `contacts[]`, `city`, `categories[]`, `leadTimeDays`, `paymentTermsDays`,
  `minOrderAmount`, `notes`, `tags` (`mareyeur`, `producteur`, `ostreiculteur`, `importateur`, `grossiste`).
- `SupplierPrice` (`supplierId`, `productId`, `price`, `updatedAt`): the last known price at each supplier. Key
  products have 2 or 3 possible suppliers. No route updates this price.
- `PurchaseOrder` (`number` "ACH-2026-000045", `supplierId`, `status`, `expectedDate`, `totalHt`, `note`) and its
  lines (`productId`, `qty`, `unitPrice`, `receivedQty`).
- `PurchaseOrder.status`: `draft` → `sent` → `partially_received` → `received`, or `cancelled`. Lines can only be
  modified in `draft`.
- Routes: `/api/purchase-orders` (create, lines, `/send`, `/receive`, `/cancel`), `/api/suppliers`,
  `/api/suppliers/{id}/usual` (what is usually bought from this supplier).
- Non-blocking alerts: `below_min_order`, `not_in_supplier_catalog`, `price_above_usual` (more than 10% above the
  last known price).
- Agent tools: `get_supplier_history`, `log_supplier_event` (quality, delay, shortage, price rise), `get_context`
  with `entityType: "supplier"`. **No purchasing tool**: creating or sending a supplier order requires writing the
  tool (the routes exist).
- Supplier persona profiles: `./data/context/suppliers/`.
- Pages: **Achats**, purchase order detail, **Fournisseurs**, supplier detail, **Historique**.
- **Rule.** A supplier order is compared with the last known price (`SupplierPrice`) and the supplier's minimum
  before being sent.

### Stock, lots and dates

**What it is.** What is really in the cold room, lot by lot, with each lot's expiry date.

**Vocabulary.**

- *Lot*: one arrival of a product, with its receipt date, its expiry date and its supplier.
- *DLC*, *DDM*: see "The trade's rules". In the pack, "DLC" means the shelf life in days after receipt.
- *FEFO* (*first expired, first out*): the lot that expires soonest goes out first.
- *Stock physique* (physical stock, what's in the cold room), *stock réservé* (reserved stock, promised to
  confirmed orders), *stock disponible* (available stock, physical minus reserved), *à recevoir* (incoming, ordered
  from the supplier, not yet arrived).
- *Casse*, *perte*, *démarque*, *destruction* (breakage, loss, shrinkage, destruction): what is thrown away.
- *Déclassement* (downgrading): a product no longer good-looking enough for its normal use, sold cheaper or
  processed.
- *Inventaire* (stock count): the actual count, which corrects the theoretical stock.

**How it works.** Each receipt creates a lot. When an order is confirmed, the quantity is reserved. At picking and
when the truck leaves, the goods go out FEFO. At the night inventory, what is past its date is destroyed and counted
as a loss. A good seller can say on the phone: "Il m'en reste 12 kilos, DLC jeudi." ("I've got 12 kilos left,
use-by Thursday.")

**The challenges.**

- Fresh fish keeps three or four days, mackerel three. Every lot that ages must find a taker.
- Theoretical stock and real stock diverge (weighings, breakage, entry errors).
- A lot that expires soon is an opportunity: offer it to the clients who take it, at a clearance price.
- A stock-out announced too late does more damage than one announced early: Les Docks want to be told 48 h ahead,
  the Vitry central kitchen 72 h ahead, in writing.

**In the ERP.**

- `Lot`: `productId`, `supplierId`, `purchaseOrderId`, `qtyReceived`, `qtyRemaining`, `receivedAt`, `expiresAt`.
  When a purchase order is received, `expiresAt` = receipt date + `Product.shelfLifeDays`.
- `StockLevel` (computed, never stored): `onHand` = sum of `qtyRemaining`; `reserved` = quantities of `confirmed` or
  `prepared` orders (prepared quantity if known); `available` = `onHand` − `reserved`; `incoming` = what remains to
  be received on `sent` or `partially_received` purchase orders; `nextExpiry`.
- Reservation is done **per product**, not per lot. Lots are only consumed (FEFO) at delivery
  (`POST /api/orders/{id}/deliver`).
- `StockMovement.reason`: `receipt` | `sale` | `adjustment` | `waste` | `return`.
- Routes: `GET /api/stock`, `GET /api/stock/movements?productId=`, `POST /api/stock/adjust` (`reason` `adjustment`
  or `waste`; `waste` always removes).
- Expired lots are **not** destroyed automatically: a `waste` via `/api/stock/adjust` is needed.
- Agent tool: `get_product_stock` (available, physical, reserved, incoming, next expiry date, list price). There is
  no stock movement tool.
- Page: **Stocks** (lots, use-by dates, movements).
- **Rule.** Announce the **available** stock (`available`), never the physical stock: the rest is already promised.
- **Rule.** If available stock isn't enough, look at `incoming` and the purchase order's expected date before saying
  "out of stock".

### Picking and weighing

**What it is.** At night, the pickers take each order, choose the lots, weigh, pack under ice and label.

**Vocabulary.**

- *Préparation*, *picking*: taking the products from the cold room.
- *Poids réel*, *poids variable* (actual weight, variable weight): what the delivered goods really weigh.
- *Écart de pesée* (weight variance): difference between ordered and delivered.
- *Colis*, *caisse*, *bac*, *étiquette* (parcel, case, tub, label — product, lot, date, origin).
- *Habillage* (dressing): gutting, scaling, filleting, portioning. The chef often asks for "vidé", "sans tête", "en
  filets" ("gutted", "head off", "filleted").

**How it works.** The client orders 6 kilos; they're delivered a fish of 5.8 or 6.3 kilos. The invoice follows the
actual weight. In the pack, the normal variance on fish sold by the kilo is −4% to +6%. Preparation requests
("vidé", "sans tête") are notes on the line. A prepared order is weighed and packed: changing it disrupts
everything.

**The challenges.**

- Keeping variances reasonable and explaining them: Brasserie Montparnasse 1925 often disputes weights and pays its
  invoices minus the variances it estimates.
- Last-minute orders arrive during picking.
- Knowing what can still be changed at the time of the call.

**In the ERP.**

- `OrderLine.preparedQty`: the quantity actually prepared. If it exists, the total and the invoice are computed from
  it, otherwise from `qty`. `OrderLine.note`: "vidé", "sans tête", "bien frais".
- Route: `POST /api/orders/{id}/prepare` (with or without quantities per line; an unlisted line is prepared exactly
  as ordered). Moves the order from `confirmed` to `prepared`.
- No picking tool for the agent.
- Page: order detail (ordered, prepared columns).
- **Rule.** Before promising a change, look at `Order.status`: `draft` or `confirmed` = modifiable; `prepared` =
  only the prepared quantity and the note change; `delivered` or later = too late, it's a complaint or a return.
- **Rule.** When a client asks for a total price for a product sold by weight, specify that it's an estimate and
  that the invoice will follow the actual weight.

### Deliveries and delivery runs

**What it is.** Refrigerated trucks that deliver each client within a time slot, following delivery runs per zone
(see "Transport"). In the pack: six delivery runs leave Rungis between 5 and 6 a.m.

**Vocabulary.**

- *Tournée*, *zone*, *jours de tournée*, *heure de départ* (delivery run, zone, run days, departure time).
- *Arrêt*, *ordre des arrêts*, *heure estimée*, *créneau* (stop, stop order, estimated time, time slot).
- *Chauffeur-livreur*, *quai*, *porte de service*, *clé* (delivery driver, dock, service entrance, key — delivery
  when the client is absent).
- *Retour*, *refus à la livraison*, *client absent* (return, refusal at delivery, client absent).
- *Affrètement* (chartering): renting a truck or handing over to a carrier.

**How it works.** Each client belongs to a zone, served by a delivery run on certain days. A client can only be
delivered on days when their run operates **and** that are among their delivery days. A run groups the day's
confirmed orders in a precise order. The driver leaves, delivers, brings back returns and sometimes money (payment
to the driver for Phở Saigon 13 or Le Festin Nomade).

**The challenges.**

- "Vous me livrez à quelle heure ?" ("What time are you delivering?"), "je ne serai pas là avant 7 h" ("I won't be
  there before 7"), "livrez par la porte de service" ("deliver through the service entrance"): these questions come
  in all morning.
- A delay breaks a restaurant's service or a central kitchen's production.
- Truck capacity is limited: on Saturdays and holidays, a second truck is needed.
- Each client's own constraints: dock no. 2 before 7 a.m., delivery Wednesday to Saturday only, blue lobster only on
  Fridays and Saturdays.

**In the ERP.**

- `Route`: `name`, `zone`, `driver`, `vehicle`, `capacityKg`, `days`, `departureTime`.
- `RouteRun`: a route on a date (`routeId`, `date`, `status`: `planned` | `in_progress` | `done`) with its
  `stops[]` (`orderId`, `clientId`, `seq`, `eta`, `status`: `pending` | `delivered` | `failed`, `note`).
- Confirming an order attaches it to the run for the client's zone on its date (`Order.routeRunId`). A draft order
  is on no delivery run.
- `eta` = departure time + 12 minutes per stop (simple calculation). Weight for capacity: kg and liters as is, a
  parcel (`box`) ≈ 5 kg, a piece or a dozen ≈ 1 kg.
- Routes: `GET /api/routes`, `GET /api/route-runs?date=`, `POST /api/route-runs/plan`,
  `PATCH /api/route-runs/{id}/stops` (reorder).
- Missing: carriers, truck booking, per-client time slots, GPS tracking. Delivery constraints are in the context
  (`kind: "logistics"`) and in `context/06-livraisons-zones.md`.
- No delivery-run tool for the agent: "where's my truck?" requires writing the tool.
- Page: **Tournées**.
- **Rule.** For "what time will I be delivered?": find the client's order for the day, its `RouteRun`, the stop and
  its `eta`. Failing that, give the run's time window.
- **Rule.** A `no_route` alert means the zone's run doesn't operate that day: offer the next delivery day.

### Invoicing, payments and receivables

**What it is.** Invoicing each delivery and getting paid. It's often the hardest part.

**Vocabulary.**

- *Facture* (invoice), *relevé* (statement, an invoice grouping several deliveries), *avoir* (credit note, a
  negative invoice after a return or a dispute).
- *Échéance* (due date), *délai de paiement* (payment terms, "30 jours"), *paiement comptant* (cash payment),
  *paiement à la livraison* (payment on delivery).
- *Encaissement*, *règlement* (receipt, payment), *lettrage* (matching a payment with the invoices it pays).
- *Encours* (outstanding): what the client owes. *Échu* (overdue): what is late. *Balance âgée* (aged balance): the
  outstanding by lateness bucket (not yet due, 1-30 days, 31-60…).
- *Relance* (reminder), *mise en demeure* (formal notice), *recouvrement* (collection), *plan d'apurement*
  (repayment plan, spreading out a debt).
- *Plafond de crédit* (credit limit), *client bloqué* (blocked client), *déblocage* (unblocking).
- *DSO*: clients' average payment delay, in days.

**How it works.** Generally, one invoice per delivery, with a due date according to the client's terms. Some
clients receive a weekly or monthly statement. Payments arrive by transfer (often one transfer for several
invoices), cheque, card, cash to the driver or direct debit. Some pay late; the accountant sends reminders with the
exact number, date and amount of each invoice. Beyond the limit or after too much delay, the client is blocked: no
more deliveries until they've paid.

**The challenges.**

- A client who doesn't pay costs more than a lost client.
- Blocking tactfully: a blocked client who calls at 3 a.m. to order must be received well, but no order may go out.
- Slow payers aren't all at risk: a public institution pays at 45-60 days but always pays; it shouldn't be blocked.
- Disputes block payments: a contested invoice stays partially paid.

**In the ERP.**

- `Invoice`: `number` "FAC-2026-000210", `clientId`, `orderIds[]`, `status`, `issuedAt`, `dueDate`, `lines[]`,
  `totalHt`, `totalVat`, `totalTtc`, `amountPaid`. `dueDate` = `issuedAt` + `Client.paymentTermsDays`.
- Stored `Invoice.status`: `draft` | `issued` | `partially_paid` | `paid` | `cancelled`. **`overdue` is never
  stored**: it is computed on read (open invoice whose `dueDate` < `meta.today`).
- `Payment`: `clientId`, `amount` (€ incl. VAT), `method` (`transfer` | `card` | `cheque` | `cash` |
  `direct_debit`), `receivedAt`, `reference`, `allocations[]`. Without allocations, the payment settles the oldest
  open invoices first.
- Receivables: `GET /api/receivables` (aged balance per client: buckets `current`, `d1_30`, `d31_60`, `d61_90`,
  `d90plus`, `avgDaysToPay`, `risk`, DSO). `risk` = `high` if outstanding > limit, more than 60 days late, client
  blocked, or pays on average at more than 60 days with something overdue; `watch` if outstanding > 80% of the
  limit, more than 30 days late, an open `late_payment`, or pays on average at more than 45 days.
- `Client.creditLimit` is in € incl. VAT; `Client.paymentTermsDays` = 0 means payment on delivery.
- Routes: `GET /api/invoices?clientId=&status=` (accepts `open` and `overdue`), `GET /api/invoices/{id}`,
  `POST /api/orders/{id}/invoice` (one invoice per delivered order), `GET/POST /api/payments`.
- Missing: credit notes as documents (only `credit_note` events in the history), automatic grouped statements, late
  payment penalties.
- Agent tools: `get_client` returns `outstanding`, `overdue`, `creditLimit`, `paymentTermsDays`. There is no tool to
  list invoices or record a payment (the README example, `list_overdue_invoices`, shows how to write one).
- Pages: **Factures**, **Paiements**, **Encours**.
- **Rule.** The backend **does not prevent** confirming an order for a `blocked` client or one beyond their limit:
  it only returns the `client_blocked` and `credit_limit` alerts. The business rule, in
  `context/05-prix-et-credit.md`: for a blocked account, no confirmed order, at most a draft with a note, and it's
  passed on to the sales rep or accounting.
- **Rule.** If an order would exceed the limit: don't refuse curtly; save it as a draft with a note, warn politely,
  pass it on. If the client has overdue amounts, say so tactfully and suggest a payment.
- **Rule.** In a reminder, always cite the exact number, date and amount. Never recite from memory: reread the
  invoices.

### Complaints, returns and disputes

**What it is.** Everything that goes wrong after delivery: damaged product, missing, wrong size grade, badly
prepared, delivered late, price or weight error. And, on the supplier side: poor-quality lot, incomplete delivery,
unexpected price rise.

**Vocabulary.**

- *Réclamation*, *litige*, *dossier ouvert*, *dossier résolu* (complaint, dispute, open case, resolved case).
- *Retour marchandise* (goods return), *refus à la livraison* (refusal at delivery: the chef sends back to the
  driver what isn't right).
- *Avoir* (credit note): amount refunded or deducted from the next invoice.
- *Geste commercial* (goodwill gesture): a discount to repair the relationship.
- *Remplacement* (replacement): redelivering the right product.
- *Risque de départ* (churn risk): a client threatening to go elsewhere.

**How it works.** The client calls or the driver reports the problem. You note precisely: product, quantity, lot,
delivery date, what the client says. The case is opened. The sales rep decides the response (credit note,
replacement, gesture), accounting issues the credit note. The case is resolved. Example from the pack: La Table
d'Aurélien refused 1 kg of langoustines that weren't lively enough on 18/11, deducted from the invoice. On the
supplier side, the buyer in turn files a claim: supplier credit note, replacement, or a price reduction on the next
order.

**The challenges.**

- A client who calls back about a complaint already open wants it to be remembered, without having to explain
  everything again.
- An agent that ignores the ongoing dispute and cheerfully offers a new order loses the client.
- Not promising on the phone what only the sales rep can grant.
- Linking a client complaint to its lot and its supplier.

**In the ERP.**

- `ClientEvent`: `type` (`onboarding`, `call`, `visit`, `complaint`, `quality_issue`, `delivery_issue`, `return`,
  `credit_note`, `dispute`, `late_payment`, `payment_plan`, `price_negotiation`, `special_request`, `menu_change`,
  `contact_change`, `compliment`, `churn_risk`, `won_back`, `note`), `title`, `description`, `channel`, `author`,
  `severity` (`low` | `medium` | `high`), `status` (`open` | `resolved`), `resolution`, `orderId`, `invoiceId`,
  `productIds`, `amount`.
- `SupplierEvent`: same fields, `type` among `quality_issue`, `delivery_issue`, `shortage`, `return`,
  `credit_note`, `dispute`, `price_change`, `price_negotiation`, `invoice_issue`, `payment`, `contract`,
  `certification`, `contact_change`, `compliment`, `call`, `visit`, `onboarding`, `note`; link
  `purchaseOrderId`.
- Routes: `GET/POST /api/clients/{id}/events`, `PATCH /api/client-events/{id}` (resolve), same on the supplier
  side.
- Tools: `get_client_history` and `get_supplier_history` (open cases first), `log_client_event` and
  `log_supplier_event` (problems are created `open`). `get_client` already returns `openIssues` and the last 5
  events.
- Missing: a goods-return endpoint (the `return` movement reason exists, not the route), credit notes as documents,
  the automatic link lot → clients delivered.
- Page: **Historique** (clients and suppliers), history tabs on the profiles.
- **Rule.** Start every client call with their open cases (`openIssues`). Talk about them before selling.
- **Rule.** During the call, record the complaint faithfully (`log_client_event`), without promising a credit note
  or a gesture. A durable fact (preference, constraint) goes into the context (`save_context`), not into the
  history.

### Seasons and hazards

**What it is.** The calendar, the weather and current events decide almost everything: what can be bought, what
clients want, at what price.

**Vocabulary.**

- *Saison* (season), *ouverture* (opening, start of fishing for a species, like scallops in October), *fermeture*
  (closing).
- *Pic*, *creux*, *fêtes*, *pont* (peak, trough, holidays, long weekend).
- *Coup de mer*, *débarque nulle*, *pénurie* (rough sea, no landing, shortage).
- *Prévision*, *anticipation*, *pré-commande de fêtes* (forecast, anticipation, holiday pre-order).

**How it works.**

- **Year end**: oysters, lobsters, langoustines, scallops, smoked salmon. Volumes multiply, caterers pre-order weeks
  in advance (Maison Berthier has a draft for 19/12), brasseries negotiate their volumes (Le Mazarin expects a
  proposal before 1 December). You have to reserve with suppliers and rent trucks.
- **August**: Paris restaurants close, volumes drop, some pay late (L'Écume).
- **School holidays**: canteens stop (the Issy central kitchen isn't delivered).
- **Lent, Easter, Fridays**: more fish. **Summer**: more beverages, fruit, light products.
- **Weather**: a storm blocks fishing for several days (right now: no landing at Le Guilvinec since Friday); a heat
  wave changes demand and threatens the cold chain; a frost destroys a harvest.
- **Day of the week**: fishmongers order more at the end of the week; Marée Bleue orders big on Tuesdays.

**The challenges.** Anticipating volumes, warning clients of a stock-out before they discover it, offering the right
seasonal products, adjusting purchases, reserving capacity.

**In the ERP.**

- Three years of order history: the seasons show in it (`GET /api/orders?date=`, `/api/clients/{id}/usual`).
- `Product.active` (out of season = inactive), `Product.tags` (`saison`, `fetes`).
- `PriceRule.validFrom` / `validTo` for dated promotions ("Ouverture de la Saint-Jacques : −5 % en octobre" —
  "Scallop season opening: −5% in October").
- The day's situation: `context/01-entreprise.md` ("Situation au 24/11" — "Situation as of 24/11") and open
  `shortage` supplier events.
- Missing: sales forecasting, weather, holiday calendar. Everything is to be built if you need it.

---

## Quick map: trade → ERP

| Trade concept | Entity, field | Main route | Agent tool | Page |
|---|---|---|---|---|
| Recognizing a client, a product | — | `GET /api/search?q=` | `search` | ⌘K |
| Client profile, the usual | `Client`, `Client.notes`, usual basket | `GET /api/clients/{id}`, `/usual` | `get_client` | **Clients** |
| What is known about a client, supplier, product | `ContextEntry` (`entityType` + `entityId`, `kind`) | `GET /api/context/for` | `get_context`, `search_context`, `save_context` | **Contexte** |
| Order taking | `Order`, `OrderLine` | `POST /api/orders`, `/lines`, `/confirm` | `create_draft_order`, `add_order_line`, `confirm_order`, `get_order` | **Commandes** |
| Modifying, cancelling an order | `Order.status` | `PATCH /api/orders/{id}`, `PATCH`/`DELETE …/lines/{lineId}`, `/cancel` | to be written | **Commandes** |
| Stock, use-by dates | `Lot`, `StockLevel`, `StockMovement` | `GET /api/stock`, `/api/products/{id}` | `get_product_stock` | **Stocks** |
| Replacement | `Product.category` | `GET /api/products/{id}/alternatives` | `find_alternatives` | **Produits** |
| Price for a client | `ClientPrice`, `PriceRule`, `Product.price` | `GET /api/prices/resolve` | `get_price` | **Prix** |
| Purchasing | `PurchaseOrder`, `SupplierPrice`, `Supplier` | `/api/purchase-orders` | to be written | **Achats**, **Fournisseurs** |
| Picking, weighing | `OrderLine.preparedQty` | `POST /api/orders/{id}/prepare` | to be written | order detail |
| Delivery runs, delivery time | `Route`, `RouteRun`, `RouteStop.eta` | `GET /api/route-runs?date=` | to be written | **Tournées** |
| Invoices, late payments | `Invoice` (`overdue` computed) | `GET /api/invoices` | to be written (`get_client` gives the totals) | **Factures** |
| Payments | `Payment.allocations` | `GET/POST /api/payments` | to be written | **Paiements** |
| Receivables, risk | aged balance, `risk` | `GET /api/receivables` | to be written | **Encours** |
| Complaints, history | `ClientEvent`, `SupplierEvent` | `/api/clients/{id}/events`, `/api/suppliers/{id}/events` | `get_client_history`, `log_client_event`, `get_supplier_history`, `log_supplier_event` | **Historique** |
| Client, product, supplier groups | `tags`, `TagDef` | `/api/tags` | — | **Groupes** |
| What the agent did | `ActivityEvent` (`actor`: `user`, `ai_chat`, `voice_agent`, `system`) | `GET /api/events`, `/api/events/stream` | automatic (`x-actor`) | **Activité** |
| Today's date | `Meta.today` | `GET /api/meta` | in the prompt | — |

**The company's memory.** Two sources, not to be confused:

- The `DATA_DIR/context/*.md` files (company presentation, typical day, product glossary, client playbook, prices
  and credit, deliveries and zones) are put **in full** into the system prompt and reread every turn
  (`apps/ai/app/agent/prompts.py`). They can be edited live.
- The context table (`ContextEntry`) contains short entries attached to an entity: `entityType` (`company` |
  `client` | `supplier` | `product` | `category`) + `entityId` (`cli_…`, `sup_…`, `prd_…`, or the id of a category
  from `GET /api/categories`). `kind`: `policy` (rule), `procedure`, `preference`, `fact`, `relationship`,
  `pricing`, `logistics`, `risk`. `source`: `seed`, `user`, `ai_chat`, `voice_agent`. `GET /api/context/for`
  returns the entity's entries **and** the linked entries (a product's department, the company rules that mention
  its id).

**What the kit doesn't model** (to be built if your problem needs it): carriers and truck booking, tasks and
reminders ("call the chef back when the turbot arrives"), quotes, credit notes as documents, goods returns, tenders,
sales forecasts, temperatures, the supplier's lot number, the link lot → clients delivered, an order cut-off time
enforced by the backend, actually blocking a blocked client's orders.

---

## Where voice changes the game

The phone is the trade's first channel. Here, player by player, are the calls that really happen every day. It's a
description of the field, not a list of topics: it's up to you to choose the problem that interests you.

### The client calling the wholesaler

- **The night order.** 3:40 a.m., Marie from the Comptoir calls for a group at lunchtime. She asks the price of cod
  loin, finds it expensive, accepts half cod, half hake on advice, adds mussels and gutted mackerel. Her outstanding
  balance is close to the limit: she has to be told without being offended.
- **"Comme d'habitude" ("the usual").** The client doesn't give details. You have to know their usual basket, offer
  it to them, and note what changes this week.
- **The stock-out.** The chef at La Table d'Aurélien wants wild turbot; there hasn't been any since the storm. He
  refuses farmed. You have to say so right away, offer what's acceptable to him (John Dory, line-caught sea bass),
  and promise to call him back when the turbot arrives.
- **The order that's too late.** Le Petit Mareyeur calls at 5:45 a.m. when its delivery run left at 5:30. You have
  to say so clearly and offer the next day.
- **The change.** The manager of Brasserie Montparnasse 1925 raises his oysters from 33 to 45 dozen, adds brown
  crabs, hesitates, changes his mind. Possible or not depending on the order's state, and he has a weight dispute in
  progress.
- **"Il est où le camion ?" ("Where's the truck?")** 6:20 a.m., Le Mazarin's oyster shucker has to set up his oyster
  stand. He needs the estimated time of his stop, the driver's name, the order's contents, and he takes the
  opportunity to add two cases of lemons.
- **The complaint.** "Les langoustines sont arrivées mortes." ("The langoustines arrived dead.") Listen, note
  precisely, promise nothing, reassure, escalate.
- **The blocked client.** La Poissonnerie Daguerre wants to order even though its account is suspended. Stay
  courteous, explain, confirm nothing, pass it on.
- **The prospect.** A new restaurant asks for prices and delivery days. Welcome them, ask the right questions
  (volumes, days, key products, current supplier), give list prices, offer a call back from the sales rep.
- **The extra.** The hotel chef orders an extra that the stores department must approve.
- **The simple question.** "Vous avez des Saint-Jacques ? À combien ? Jusqu'à quand je peux commander pour
  demain ?" ("Do you have scallops? How much? Until when can I order for tomorrow?")

### The wholesaler calling its clients

- **Announcing a stock-out** before the client discovers it at delivery, with an alternative and its price.
- **Offering an arrival or a lot to clear**: "J'ai de très beaux homards ce matin" ("I have some very fine lobsters
  this morning"), "Il me reste 15 kilos de lieu jaune, je vous les fais à…" ("I have 15 kilos of pollack left, I'll
  do them for you at…") (the price is decided by the sales rep).
- **Chasing an unpaid invoice**: cite the invoices, get a payment date, note it.
- **Waking up a silent client**: they ordered three times a week, nothing for ten days.
- **Preparing the holidays**: collecting pre-orders from caterers and brasseries.

### The wholesaler and its suppliers

- **Comparing and negotiating**: calling two or three fish wholesalers, getting a price, negotiating on volume.
- **Reserving a rare lot** or asking for a **balance delivery** after an incomplete delivery.
- **Filing a claim**: out-of-grade lot, incomplete delivery, delay.
- **Being called**: the supplier announces a storm, a price rise, a delay; or chases a payment.

### The wholesaler and transport

- **Booking an extra truck** for a busy Saturday: volume, temperature, time, dock, price.
- **The driver calling in**: client absent, access blocked, goods refused, delay on the run.

### Internally

- **A colleague asks about stock**: "Il nous reste quoi en Saint-Jacques ?" ("What have we got left in scallops?")
  The right answer gives the available stock, the lots ending soon and tomorrow's arrival.
- **The sales rep on the road** dictates a note after a visit, or asks a client's outstanding balance before going
  in.
- **The manager** asks where unpaid invoices stand, the day's stock-outs, the night's orders.
- **The picker** reports a weight variance or a missing product during picking.

These situations are all test scenarios: write your own from your company's client and supplier profiles
(`data/context/`).

---

## Why it's hard for an agent

Everything happens at the same time, at night, on the phone, with busy people who talk fast, with noise, with their
own words. Every answer must be right to the kilo and to the cent. The agent must have the memory of the best sales
rep (who this client is, what they take, what annoys them, what happened last week), the rigor of an accountant
(outstanding, limit, due dates) and the caution of a quality manager (no substitution without agreement, no
impossible promise), all at the speed of a normal conversation.

What makes an agent sound like a pro:

- it recognizes the client and calls them by their first name;
- it speaks in the trade's units ("six kilos de sole 500-600", "trente douzaines de n° 3" — "six kilos of 500-600
  sole", "thirty dozen no. 3");
- it offers the usual instead of asking ten questions;
- it announces a stock-out with a reason and an alternative;
- it knows the real delivery day and time;
- it reads the order back before hanging up;
- it only promises what the company can deliver.

---

## Glossary

| Term (French — English) | Definition | In the ERP |
|---|---|---|
| Affrètement — chartering | Renting a truck or handing a delivery to a carrier | absent |
| Alias | Common name of a product ("loup" for sea bass / "bar") | `Product.aliases` |
| AOP, Label Rouge — PDO, Red Label | Official quality or origin marks | `Product.tags` (`labels`) |
| Arrivage, débarque — arrivals, landing | Goods coming in, what the boats bring back | `PurchaseOrder`, `Lot` |
| Avoir — credit note | Negative invoice after a return or a dispute | `credit_note` event |
| Balance âgée — aged balance | Receivables broken down by how late they are | `GET /api/receivables` |
| BL (bon de livraison) — delivery note | Document that accompanies the delivery | — |
| Bordereau de prix — price schedule | Prices fixed by a public contract | `ClientPrice`, `PriceRule` (`marche-public`) |
| Bourriche — oyster basket | Basket of oysters (e.g. 4 dozen) | unit `dozen` |
| Brouillon, pré-commande — draft, pre-order | Order not yet confirmed by the client | `Order.status = "draft"` |
| Calibre — size grade | Size of a product (1-2 kg, 15/20, no. 3) | `Product.caliber` |
| Chaîne du froid — cold chain | Continuous temperature control | — |
| Colis, caisse — parcel, case | Packaging unit | unit `box` (≈ 5 kg) |
| Commande d'achat — purchase order | Order placed with a supplier | `PurchaseOrder` |
| Commercial attitré — assigned sales rep | Salesperson responsible for a client | `Client.salesRep` |
| Complément — balance delivery | Remainder of an incomplete delivery, delivered later | `partially_received` |
| Couverture — stock cover | Number of days of sales the stock can sustain | — |
| Criée — fish auction | Hall where the catch is sold at auction | — |
| Cut-off, heure limite — cut-off time | Time after which the order goes to the next day | context only |
| DDM — best-before date | Minimum durability date, "best before" | — |
| Déclassement — downgrading | Product sold cheaper or processed because it looks less good | — |
| Démarque, perte, casse — shrinkage, loss, breakage | What gets thrown away | `waste` movement |
| DLC — use-by date | Use-by date, "use by" | `Lot.expiresAt`, `Product.shelfLifeDays` |
| Disponible — available | Physical stock minus reserved stock | `StockLevel.available` |
| DSO | Average client payment delay (days sales outstanding) | `GET /api/receivables` |
| Échéance — due date | Date by which the invoice must be paid | `Invoice.dueDate` |
| Échu, en retard — overdue | Invoice unpaid after its due date | computed status `overdue` |
| Encours — outstanding balance | Total owed by a client, € incl. VAT | `outstanding` |
| Extra — one-off | One-off order outside the usual pattern | — |
| FEFO | First expired, first out | `fefo_lots` in `services/stock.py` |
| Franco — free-shipping threshold | Amount above which transport is free | `Supplier.notes` |
| Geste commercial — goodwill gesture | Discount granted to fix a problem | event + `resolution` |
| HACCP | Hazard analysis method for food hygiene | — |
| L'habituel — the usual | What the client almost always orders | `GET /api/clients/{id}/usual` |
| Lot | One arrival of a product, with its expiry date | `Lot` |
| Mareyeur — fish wholesaler | First buyer of the fish at the auction, who prepares and ships it | `Supplier.tags` (`mareyeur`) |
| Marché public — public contract | A public body's purchasing contract after a tender | client tag `marche-public` |
| Mercuriale — price list | A supplier's price list of the day | `SupplierPrice` |
| MIN — national wholesale market | Marché d'intérêt national (Rungis, Lyon, Marseille…) | — |
| Minimum de commande — minimum order | Minimum amount to order from a supplier | `Supplier.minOrderAmount` |
| Plafond de crédit — credit limit | Maximum outstanding balance allowed | `Client.creditLimit` |
| Plan d'apurement — repayment plan | Schedule for paying off a debt | `payment_plan` event |
| Poids réel — actual weight | What the delivered goods actually weigh | `OrderLine.preparedQty` |
| Prix liste, catalogue — list price | Base price | `Product.price` |
| Prix négocié — negotiated price | A product's price for a specific client | `ClientPrice` |
| Prospect | Potential client | `Client.status = "prospect"` |
| Relance — reminder | Reminder for an unpaid invoice | `late_payment` event |
| Réservé — reserved | Stock promised to confirmed orders | `StockLevel.reserved` |
| RHD — food service | Restauration hors domicile (out-of-home catering) | — |
| Rupture — stock-out | No more stock available | `insufficient_stock` alert |
| Substitution | Product delivered instead of another, with agreement | `OrderLine.substituteFor` |
| Tournée — delivery run | A truck's circuit over a zone, on certain days | `Route`, `RouteRun` |
| Zone | A client's delivery area | `Client.zone` = `Route.zone` |
