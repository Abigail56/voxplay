import type { Metadata } from "next";
import localFont from "next/font/local";

import { Nav } from "@/components/Nav";

import "./globals.css";

// Fraunces (SIL OFL, see fonts/Fraunces-OFL.txt), bundled so the build never needs the network.
// Headings only; body text stays in the system font.
const display = localFont({
  src: [
    { path: "./fonts/fraunces-latin-500-normal.woff2", weight: "500", style: "normal" },
    { path: "./fonts/fraunces-latin-500-italic.woff2", weight: "500", style: "italic" },
    { path: "./fonts/fraunces-latin-600-normal.woff2", weight: "600", style: "normal" },
    { path: "./fonts/fraunces-latin-600-italic.woff2", weight: "600", style: "italic" },
  ],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "Who's Talking?",
  description: "An online voice game and speaker-recognition lab (ECAPA-TDNN, Whisper, FastAPI, pgvector)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={display.variable}>
      <body>
        <main>
          <Nav />
          {children}
        </main>
      </body>
    </html>
  );
}
