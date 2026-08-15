/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "../shared/macro-shell/**/*.{js,ts,jsx,tsx}",
    "../shared/ai-assistant/**/*.{js,ts,jsx,tsx}",
    "../shared/stats-glossary/**/*.{js,ts,jsx,tsx}",
  ],
  theme: { extend: {} },
  plugins: [],
};
