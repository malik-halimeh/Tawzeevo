import { expect, test } from "vitest";

import { notificationText } from "./notifications";

const item = { id: "n1", kind: "PAYMENT_RECORDED", data: { amount: "12.5000", currency: "USD", invoice_number: "2026-000007" }, created_at: "2026-09-27T09:00:00Z", read: false };

test("a recorded payment reads the same in English and Arabic, amounts as the server sent them (D-114)", () => {
  expect(notificationText("en", item)).toBe("Payment of 12.50 USD received for invoice 2026-000007. Thank you.");
  expect(notificationText("ar", item)).toBe("استُلمت دفعة بقيمة 12.50 USD للفاتورة 2026-000007. شكراً لك.");
  expect(notificationText("en", { ...item, kind: "SOMETHING_NEW" })).toBe("A message from the shop.");
});
