/**
 * Tenant-calendar day (D-040): business days are resolved on the Asia/Beirut calendar, which is
 * what the API uses for demand ranges, overdue ages and analytics periods. `new Date()
 * .toISOString().slice(0, 10)` is the UTC date and is still "yesterday" between 00:00 and 03:00
 * local, so defaults derived from it silently missed the current day's demand.
 */
export const TENANT_TIME_ZONE = "Asia/Beirut";

const formatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: TENANT_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** ISO calendar date (YYYY-MM-DD) of `at` on the tenant calendar. */
export function tenantCalendarDate(at: Date = new Date()): string {
  // en-CA renders numeric dates as YYYY-MM-DD; parts are used so a locale change cannot break it.
  const parts = formatter.formatToParts(at);
  const pick = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return `${pick("year")}-${pick("month")}-${pick("day")}`;
}
