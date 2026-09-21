/**
 * D-040 tenant-calendar day (audit finding TWZ-F-031): the default demand range must be the
 * Asia/Beirut day the server resolves, not the UTC date.
 */
import { describe, expect, it } from "vitest";
import { tenantCalendarDate } from "./tenantCalendar";

describe("tenantCalendarDate", () => {
  it("is the Beirut day, which differs from the UTC date between 00:00 and 03:00 local", () => {
    // 2026-09-20T22:30Z is 2026-09-21 01:30 in Beirut (UTC+3 in September).
    expect(tenantCalendarDate(new Date("2026-09-20T22:30:00Z"))).toBe("2026-09-21");
    expect(new Date("2026-09-20T22:30:00Z").toISOString().slice(0, 10)).toBe("2026-09-20");
    // 2026-01-15T21:30Z is 2026-01-15 23:30 in Beirut (UTC+2 in winter): same day.
    expect(tenantCalendarDate(new Date("2026-01-15T21:30:00Z"))).toBe("2026-01-15");
    // 2026-01-15T22:30Z is 2026-01-16 00:30 in Beirut.
    expect(tenantCalendarDate(new Date("2026-01-15T22:30:00Z"))).toBe("2026-01-16");
  });

  it("formats as an ISO calendar date", () => {
    expect(tenantCalendarDate()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
