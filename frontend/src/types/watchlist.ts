export interface WatchlistEntry {
  symbol: string;
  sec_type: string;
  exchange: string;
  currency: string;
}

export interface WatchlistEntryPayload {
  symbol: string;
  sec_type?: string;
  exchange?: string;
  currency?: string;
}
