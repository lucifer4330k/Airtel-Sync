import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "rgb(var(--paper) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        ink: "rgb(var(--ink) / <alpha-value>)",
        "ink-soft": "rgb(var(--ink-soft) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        pen: "rgb(var(--pen) / <alpha-value>)",
        "pen-strong": "rgb(var(--pen-strong) / <alpha-value>)",
        stamp: "rgb(var(--stamp) / <alpha-value>)",
        marigold: "rgb(var(--marigold) / <alpha-value>)",
        alert: "rgb(var(--alert) / <alpha-value>)",
        chart: "rgb(var(--chart) / <alpha-value>)",
        night: "rgb(var(--night) / <alpha-value>)",
        "night-soft": "rgb(var(--night-soft) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["var(--font-plex)", "var(--font-plex-deva)", "var(--font-tamil)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "var(--font-plex)", "system-ui", "sans-serif"],
      },
      borderRadius: { bill: "6px" },
      maxWidth: { app: "30rem" },
    },
  },
  plugins: [],
};
export default config;
