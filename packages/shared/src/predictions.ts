/** Predictions (GET /api/predictions/*): the season radar and stock to rescue. Mirrors apps/backend/app/schemas/predictions.py. */
import type { Id, IsoDate } from "./domain";

export interface SeasonPeak {
  productId: Id;
  productName: string;
  unit: string;
  supplierId?: Id;
  supplierName?: string;
  leadTimeDays?: number;
  rampWeekStart: IsoDate; // Monday of the first coming week at or above the threshold
  peakWeekStart: IsoDate;
  peakIndex: number; // demand of that week / a usual week (2 = double)
  usualWeekQty: number;
  expectedPeakWeekQty: number;
  daysUntilRamp: number;
  orderBy: IsoDate; // ramp week start minus the supplier lead time
  daysToOrderBy: number; // negative = already late
  late: boolean;
  available: number;
  incoming: number; // confirmed purchase orders only, never drafts
  suggestedQty: number;
  estimatedCost?: number;
  yearsOfHistory: number;
  reason: string;
}

export interface SupplierBasket {
  supplierId: Id;
  supplierName: string;
  leadTimeDays?: number;
  minOrderAmount?: number;
  productCount: number;
  totalCost: number;
  meetsMinimum: boolean;
  orderBy: IsoDate;
}

export interface SeasonRadar {
  asOf: IsoDate;
  horizonWeeks: number;
  threshold: number;
  peaks: SeasonPeak[];
  suppliers: SupplierBasket[];
}

export interface RadarBacktest {
  asOf: IsoDate;
  horizonWeeks: number;
  announced: number;
  hits: number;
  exactWeekHits: number;
  precision?: number;
  realPeaks: number;
  found: number;
  recall?: number;
}

export interface RescueClient {
  clientId: Id;
  clientName: string;
  ordersLast90d: number;
  suggestedQty: number;
  unitPrice: number;
  offerPrice: number;
  alreadyProposed: boolean;
  askedForDeal?: string; // AI signal: this client asked for a deal in writing (why) → offered first
}

export interface RescueItem {
  productId: Id;
  productName: string;
  unit: string;
  atRiskUnits: number;
  atRiskValue: number; // at cost
  earliestExpiry: IsoDate;
  daysToExpiry: number;
  weeklySales: number;
  listPrice: number;
  cost: number;
  suggestedDiscountPct: number;
  coveredUnits: number;
  clients: RescueClient[];
  reason: string;
}

export interface StockRescue {
  asOf: IsoDate;
  horizonDays: number;
  items: RescueItem[];
}

export interface OfferInput {
  clientId: Id;
  productId: Id;
  qty: number;
  discountPct: number;
  offerPrice: number;
}

// ───────── Carnet de Noël: written holiday reservations, read by an LLM, estimated by arithmetic ─────────

/** How the LLM read a note. firm = reserves; tentative = hesitates / a question / a condition; cancelled; unclear. */
export type ReservationIntent = "firm" | "tentative" | "cancelled" | "unclear";

export interface ReservationNote {
  eventId: Id;
  clientId: Id;
  clientName: string;
  at: IsoDate;
  text: string;
  quote?: string; // what the client said, as written
  intent: ReservationIntent;
  multiplier: number;
  askedForDeal: boolean;
  condition?: string;
  aiSummary?: string;
  analyzed: boolean; // an LLM (or the rules) has read it
}

export interface ReservationLine {
  eventId: Id;
  clientId: Id;
  clientName: string;
  productId: Id;
  productName: string;
  unit: string;
  pastYears: { year: number; qty: number }[];
  baselineQty?: number; // mean of the client's own late-December quantities; absent = no history
  multiplier: number;
  qty?: number;
  unitPrice: number;
  value?: number;
  intent: ReservationIntent;
  expectedValue: number;
  ordered: boolean;
}

export interface ReservationProduct {
  productId: Id;
  productName: string;
  unit: string;
  reservedUnits: number;
  available: number;
  incoming: number;
  shortfall: number;
  supplierName?: string;
  orderBy?: IsoDate;
  late: boolean;
}

export interface HolidayReservations {
  asOf: IsoDate;
  season: number;
  notes: ReservationNote[];
  lines: ReservationLine[];
  products: ReservationProduct[];
  conversion: { rate?: number; converted: number; total: number; seasons: number[] };
  totals: {
    notes: number;
    lines: number;
    linesWithoutHistory: number;
    reservedValue: number;
    expectedValue: number;
    orderedLines: number;
    analyzedNotes: number;
    shortProducts: number;
  };
}

/** GET /api/predictions/holiday-reservations/backtest: a past season's estimate vs what clients really bought. */
export interface ReservationsBacktest {
  season: number;
  useSignals: boolean;
  lines: number;
  linesBought: number;
  notesToOrders?: number;
  wape?: number; // weighted absolute % error on units, per line
  within30Pct?: number;
  predictedValue: number;
  expectedValue: number;
  actualValue: number;
  valueError?: number; // (expected − actual) / actual
}

/** POST /ai/insights/reservations/extract */
export interface ReservationsExtract {
  season?: number;
  notes: number;
  saved: number;
  model?: string;
  byIntent: Partial<Record<ReservationIntent, number>>;
  doubled?: number;
  askedForDeal: number;
}
