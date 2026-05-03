import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ivory: "#FAF7F2",
        ink: "#1B1B1F",
        violet: {
          DEFAULT: "#5B4FE9",
          muted: "#8A82F0",
        },
        teal: {
          DEFAULT: "#0F766E",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui"],
        display: ["var(--font-fraunces)", "ui-serif", "Georgia"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(27,27,31,0.04), 0 8px 24px rgba(27,27,31,0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
