import { describe, expect, it } from "vitest";

import { foldSearchText, hasLetters } from "./searchText";

describe("foldSearchText (the server's customer-name folding)", () => {
  it("folds alef, alef maqsura and teh marbuta variants", () => {
    expect(foldSearchText("أحمد إبراهيم آمنة ٱلنور")).toBe("احمد ابراهيم امنه النور");
    expect(foldSearchText("مصطفى")).toBe("مصطفي");
    expect(foldSearchText("فاطمة")).toBe("فاطمه");
  });

  it("drops tatweel and diacritics", () => {
    expect(foldSearchText("محـــمد")).toBe("محمد");
    expect(foldSearchText("مُحَمَّدٌ")).toBe("محمد");
  });

  it("turns Arabic-Indic and Extended Arabic-Indic digits into 0-9 and lowers Latin letters", () => {
    expect(foldSearchText("٠٣١٢٣٤٥٦٧٨٩")).toBe("03123456789");
    expect(foldSearchText("۰۷۱")).toBe("071");
    expect(foldSearchText("Maya MARKET")).toBe("maya market");
  });
});

describe("hasLetters", () => {
  it("reads letters as a name and digits, spaces and + as a phone", () => {
    expect(hasLetters("ما")).toBe(true);
    expect(hasLetters("Ma")).toBe(true);
    expect(hasLetters("+961 70 123")).toBe(false);
    expect(hasLetters("٠٧٠")).toBe(false);
  });
});
