export interface DataTestField {
  key: string
  label: string
}

export type DataTestSourceName = 'interactive_service' | 'yahoo_finance' | 'finnhub' | 'fmp'

export type DataTestCellValues = Partial<Record<DataTestSourceName, number | string | null>>

export interface DataTestResult {
  fields: DataTestField[]
  symbols: string[]
  values: Record<string, Record<string, DataTestCellValues>>
  source_errors: Partial<Record<DataTestSourceName, string | null>>
}
