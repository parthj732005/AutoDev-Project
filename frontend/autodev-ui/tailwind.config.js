/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#111111",
          2: "#1a1a1a",
          3: "#222222",
        },
        border: "#2a2a2a",
        primary: {
          DEFAULT: "#6366f1",
          hover: "#4f46e5",
        },
        success: "#22c55e",
        warning: "#f59e0b",
        danger: "#ef4444",
      },
    },
  },
  plugins: [],
};
