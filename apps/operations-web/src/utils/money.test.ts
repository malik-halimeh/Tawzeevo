import { afterEach, expect, test } from "vitest";

import i18n from "../i18n";
import { formatMoney, money } from "./money";

afterEach(async () => { await i18n.changeLanguage("en"); });

const cases: [string | number, string, string][] = [
  ["1234.5000", "USD", "1,234.50 $"],
  ["42.5000", "USD", "42.50 $"],
  ["0.0125", "USD", "0.0125 $"],
  ["3.2550", "USD", "3.255 $"],
  ["3.2500", "USD", "3.25 $"],
  ["3.0001", "USD", "3.0001 $"],
  ["0.0000", "USD", "0.00 $"],
  ["12", "AED", "12.00 AED"],
  ["1234.5000", "EUR", "1,234.50 €"],
  ["0.0125", "EUR", "0.0125 €"],
  ["3.2550", "AED", "3.255 AED"],
  ["-5.0000", "USD", "-5.00 $"],
  ["-0.0125", "USD", "-0.0125 $"],
  ["-1234.5000", "EUR", "-1,234.50 €"],
  ["-12.0000", "AED", "-12.00 AED"],
  [12.5, "USD", "12.50 $"],
  [1e21, "USD", "1,000,000,000,000,000,000,000.00 $"],
  ["—", "USD", "—"],
  ["—", "LBP", "—"],
];

test.each(["en", "ar"] as const)("Western digits and currency suffixes in %s", (lang) => {
  for (const [value, currency, expected] of cases) {
    expect(formatMoney(value, currency, lang), `${value} ${currency}`).toBe(expected);
  }
});

test.each(["en", "ar"] as const)("LBP integers, fractions, rounding and large values in %s", (lang) => {
  const suffix = lang === "ar" ? "ل.ل" : "LBP";
  const pounds = [
    ["17460000.0000", "17,460,000"],
    ["9999999999999999.0000", "9,999,999,999,999,999"],
    ["9999999999999999.9950", "10,000,000,000,000,000"],
    ["17460000.1200", "17,460,000.12"],
    ["17460000.1000", "17,460,000.1"],
    ["0.0000", "0"],
    ["0.0049", "0"],
    ["0.0050", "0.01"],
    ["1.2350", "1.24"],
    ["-1.2350", "-1.24"],
    ["-17460000.0000", "-17,460,000"],
  ];
  for (const [value, expected] of pounds) {
    expect(formatMoney(value!, "LBP", lang)).toBe(`${expected} ${suffix}`);
  }
});

test("render helper follows the current language without changing the source amount", async () => {
  const value = "17460000.1250";
  await i18n.changeLanguage("ar");
  expect(money(value, "LBP")).toBe("17,460,000.13 ل.ل");
  await i18n.changeLanguage("en");
  expect(money(value, "LBP")).toBe("17,460,000.13 LBP");
  expect(value).toBe("17460000.1250");
});
