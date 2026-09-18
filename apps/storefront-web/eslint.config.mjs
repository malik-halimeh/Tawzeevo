import js from "@eslint/js";
import nextPlugin from "eslint-config-next";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...nextPlugin,
  // Product images are already bounded and re-encoded by the API; no optimizer service is used.
  { rules: { "@next/next/no-img-element": "off" } },
);
