import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0d10",
        panel: "#11161b",
        line: "#1f2a33",
        ink: "#e6edf3",
        muted: "#8b98a5",
        accent: "#5b8def",
        ok: "#3fb950",
        warn: "#d29922",
        bad: "#f85149",
      },
    },
  },
  plugins: [],
} satisfies Config;
