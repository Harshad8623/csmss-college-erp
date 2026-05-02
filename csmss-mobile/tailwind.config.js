/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        navy:    "#050d1a",
        "navy-mid": "#0b1830",
        "navy-card": "#0d1f3c",
        blue:    "#3b82f6",
        "blue-bright": "#1a56db",
        gold:    "#f59e0b",
        green:   "#10b981",
        red:     "#ef4444",
        purple:  "#8b5cf6",
        muted:   "#5a7499",
      },
    },
  },
  plugins: [],
};
