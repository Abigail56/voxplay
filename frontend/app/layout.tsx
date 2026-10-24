import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";

import { Nav } from "@/components/Nav";
import { Footer } from "@/components/portal/Footer";

import "./globals.css";

// Chakra Petch (SIL OFL, see fonts/ChakraPetch-OFL.txt), bundled so the build never needs the network.
// Headings, the wordmark and numbers; body text stays in the system font.
const display = localFont({
  src: [
    { path: "./fonts/chakra-petch-latin-500-normal.woff2", weight: "500", style: "normal" },
    { path: "./fonts/chakra-petch-latin-600-normal.woff2", weight: "600", style: "normal" },
    { path: "./fonts/chakra-petch-latin-700-normal.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: { default: "VOXPLAY · Enter the game. Own the moment.", template: "%s · VOXPLAY" },
  description: "VOXPLAY is a social gaming universe: multiplayer voice games and team quiz battles you play with friends, from your own phone.",
  applicationName: "VOXPLAY",
};

export const viewport: Viewport = { themeColor: "#080a16", colorScheme: "dark" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={display.variable}>
      <body>
        <Nav />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
