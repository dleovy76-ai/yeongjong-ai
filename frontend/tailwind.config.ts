import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        cream: "#fbf3e7",
        coral: {
          DEFAULT: "#d9713c",
          dark: "#c85f2f",
          darker: "#a3491f",
        },
        ink: "#3a2a1f",
        "ink-muted": "#6b5844",
        sky: "#7fb3c4",
        terracotta: "#b85a2a",
        sand: "#f4e9d8",
        paper: "#fffaf3",
      },
      fontFamily: {
        display: ['"Gowun Dodum"', "sans-serif"],
        sans: ['"Noto Sans KR"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
