import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Tawzeevo",
  description: "Bilingual storefronts for Cash Van businesses.",
  robots: { index: true, follow: true },
};

/** The root layout is language-neutral; each shop layout sets `lang` and `dir` on its content. */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
