export interface WatchlistEntry {
  symbol: string;
  sec_type: string;
  exchange: string;
  currency: string;
  active: boolean;
}

export interface WatchlistEntryPayload {
  symbol: string;
  sec_type?: string;
  exchange?: string;
  currency?: string;
  active?: boolean;
}
