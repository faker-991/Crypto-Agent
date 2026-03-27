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
        ink: "#101418",
        sand: "#f4efe7",
        ember: "#d97706",
        moss: "#5b6b47",
      },
    },
  },
  plugins: [],
};

export default config;
