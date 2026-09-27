import { expect, test } from "vitest";

import i18n from "../i18n";
import { distanceText, durationText, stepText } from "./directions";

const step = (type: number, name: string | null = null, exit: number | null = null) => ({ type, name, distance_m: 100, duration_s: 10, exit_number: exit });

test("turns, distances and times are worded by the app in English and Arabic", async () => {
  await i18n.changeLanguage("en");
  const t = i18n.t.bind(i18n);
  expect(stepText(t, step(0, "Charles Helou"), "Shop")).toBe("Turn left onto \u2068Charles Helou\u2069");
  expect(stepText(t, step(7, null, 2), "Shop")).toBe("At the roundabout, take exit 2");
  expect(stepText(t, step(10), "Jounieh Minimart")).toBe("Arrive at Jounieh Minimart");
  expect(stepText(t, step(99), "Shop")).toBe("Continue straight"); // an unknown code never shows a raw number
  expect(distanceText(t, 348)).toBe("350 m");
  expect(distanceText(t, 17445.8)).toBe("17 km");
  expect(distanceText(t, 3276)).toBe("3.3 km");
  expect(durationText(t, 992.5)).toBe("17 min");
  expect(durationText(t, 4000)).toBe("1 h 7 min");

  await i18n.changeLanguage("ar");
  const ar = i18n.t.bind(i18n);
  expect(stepText(ar, step(1, "شارع الأشرفية"), "دكان")).toBe("انعطف يميناً إلى \u2068شارع الأشرفية\u2069");
  expect(distanceText(ar, 3276)).toBe("3.3 كم");
  expect(durationText(ar, 60)).toBe("دقيقة واحدة");
  await i18n.changeLanguage("en");
});
