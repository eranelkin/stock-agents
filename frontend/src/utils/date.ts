const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

/** Formats a date as "DD-MMM-YYYY, HH:MM" (e.g. "05-Sep-2026, 14:32"). */
export function formatDateTime(value: string | Date): string {
  const d = typeof value === "string" ? new Date(value) : value
  const day = String(d.getDate()).padStart(2, "0")
  const month = MONTHS[d.getMonth()]
  const year = d.getFullYear()
  const hours = String(d.getHours()).padStart(2, "0")
  const minutes = String(d.getMinutes()).padStart(2, "0")
  return `${day}-${month}-${year}, ${hours}:${minutes}`
}
