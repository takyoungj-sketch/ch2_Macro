export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "../frontend-built/src/components/TwinExperimentLab.tsx",
    "../frontend-rent/src/components/ConversionComparePanel.tsx",
    "../shared/macro-shell/**/*.{js,ts,jsx,tsx}",
    "../shared/stats-glossary/**/*.{js,ts,jsx,tsx}",
    "../shared/ui-window/**/*.{js,ts,jsx,tsx}",
  ],
  theme: { extend: {} },
  plugins: [],
};
