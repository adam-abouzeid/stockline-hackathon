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
