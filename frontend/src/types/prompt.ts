export interface Prompt {
  id: string
  title: string
  content: string
  category: string
  search_enabled: boolean
  search_query_template: string | null
  search_mode: string | null
  output_schema: Record<string, unknown> | null
  is_active: boolean
  created_at: string
  updated_at: string
}
