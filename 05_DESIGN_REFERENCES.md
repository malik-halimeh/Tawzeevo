# 05_DESIGN_REFERENCES.md — User-Controlled Visual Direction

## Current status

Final visual direction: **NOT YET PROVIDED**

Until references are added:
- build clean, accessible, functional layouts;
- use semantic structure and design tokens/CSS variables;
- do not create a final brand identity;
- do not add a generic admin template dependency;
- do not change business behavior for visual convenience.

## How the user may add references

For each reference, append:

```text
Reference ID:
URL or local image/file:
Applies to:
What to borrow:
What NOT to copy:
Priority:
Arabic/RTL notes:
Mobile notes:
```

Examples of `Applies to`:
- login;
- admin users;
- owner invoice maker;
- storefront product page;
- dashboard;
- navigation;
- typography;
- motion.

## Implementation design rules

When doing design work:
1. read this file;
2. use only references relevant to the current screen;
3. preserve functionality, accessibility, responsive behavior, and RTL;
4. do not copy unrelated sections of a reference;
5. do not download/reuse copyrighted site assets unless the user has provided/approved them;
6. if a reference creates a product-behavior conflict, the product contract wins;
7. if reference intent is ambiguous, ask before making a broad visual-system decision.

## Accessibility baseline

- keyboard usable;
- visible focus;
- semantic controls;
- labels/errors;
- adequate contrast;
- reduced-motion support;
- not color-only communication;
- Arabic/English layout tested.
