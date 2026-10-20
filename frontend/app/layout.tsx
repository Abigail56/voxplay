import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Voice ID",
  description: "Speaker recognition with ECAPA-TDNN, FastAPI and pgvector",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
