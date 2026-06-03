export function resolvePlaceholders(text: string): string {
  const now = new Date();
  const formatted = new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "America/New_York",
    timeZoneName: "short",
  }).format(now);
  return text.replace(/\{CURRENT_DATE\}/g, formatted);
}
