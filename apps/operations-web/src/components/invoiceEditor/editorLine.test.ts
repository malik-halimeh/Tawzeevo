import { expect, test } from "vitest";
import { quantityValue } from "./editorLine";

test.each([["1+1", 2], [" (2 + 3) * 4 / 2", 10], ["1.5", 1.5], ["١+٢", 3], ["۲+۱", 3], ["-1+3", 2]])("quantity preview %s is %s", (expression, value) => {
  expect(quantityValue(expression)).toBe(value);
});
test.each(["", "1+", "1 1", "1/0", "alert(1)", "2**3", "(1+1", "Infinity", "99999999999999999999"])("invalid quantity %s stays unmodified and has no stepper value", (expression) => {
  expect(quantityValue(expression)).toBeUndefined();
});
