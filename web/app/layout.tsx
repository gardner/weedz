import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Weedz · Nelson / Tasman field review",
  description:
    "Open-source weed screening for conservation. Review the evidence, keep the context.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-NZ">
      <body>{children}</body>
    </html>
  );
}
