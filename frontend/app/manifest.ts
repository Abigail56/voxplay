import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "VOXPLAY",
    short_name: "VOXPLAY",
    description: "Enter the game. Own the moment. Multiplayer voice games and team quiz battles.",
    start_url: "/",
    display: "standalone",
    background_color: "#080a16",
    theme_color: "#080a16",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
