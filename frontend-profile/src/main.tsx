import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProductWall } from "@ch2/macro-shell/productAccess";
import { applyColorScheme, readStoredColorScheme } from "@ch2/macro-shell/displayUi";
import App from "./App";
import { StatsGlossaryPresentationProvider } from "@ch2/stats-glossary";
import ProfileStatsGlossaryHelp from "./components/ProfileStatsGlossaryHelp";
import "./index.css";

applyColorScheme(readStoredColorScheme());

const qc = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <ProductWall>
        <StatsGlossaryPresentationProvider component={ProfileStatsGlossaryHelp}>
        <App />
        </StatsGlossaryPresentationProvider>
      </ProductWall>
    </QueryClientProvider>
  </React.StrictMode>,
);
