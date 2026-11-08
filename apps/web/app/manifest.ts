import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Udyam Digital",
    short_name: "Udyam",
    description: "Internet, phones and billing for your business, with one monthly price.",
    start_url: "/start",
    display: "standalone",
    background_color: "#F6F7F9",
    theme_color: "#2A3A8F",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
