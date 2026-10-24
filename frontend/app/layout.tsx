import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";

import { Nav } from "@/components/Nav";
import { Footer } from "@/components/portal/Footer";

import "./globals.css";

// Both fonts are SIL OFL (see fonts/*-OFL.txt) and bundled, so the build never needs the network.
// Kanit italic: headings, the wordmark and numbers, with the punch of an anime title card.
const display = localFont({
  src: [
    { path: "./fonts/kanit-latin-700-italic.woff2", weight: "700", style: "italic" },
    { path: "./fonts/kanit-latin-800-italic.woff2", weight: "800", style: "italic" },
    { path: "./fonts/kanit-latin-900-italic.woff2", weight: "900", style: "italic" },
  ],
  variable: "--font-display",
});
// Nunito: rounded and friendly body text (one variable file covers every weight).
const body = localFont({
  src: [{ path: "./fonts/nunito-latin-variable.woff2", weight: "200 1000", style: "normal" }],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: { default: "VOXPLAY · Enter the game. Own the moment.", template: "%s · VOXPLAY" },
  description: "VOXPLAY is a social gaming universe: multiplayer voice games and team quiz battles you play with friends, from your own phone.",
  applicationName: "VOXPLAY",
};

export const viewport: Viewport = { themeColor: "#080a16", colorScheme: "dark" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body>
        <Nav />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
