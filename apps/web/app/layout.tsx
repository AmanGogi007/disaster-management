import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Location Hazard Intelligence Engine",
  description: "V0.3 — Evidence-first flood-risk assessment",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
