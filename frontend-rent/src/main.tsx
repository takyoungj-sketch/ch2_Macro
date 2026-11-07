import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { StatsGlossaryPresentationProvider } from "@ch2/stats-glossary";
import RentStatsGlossaryHelp from "./components/RentStatsGlossaryHelp";
import { ProductWall } from "@ch2/macro-shell/productAccess";
import { applyColorScheme, readStoredColorScheme } from "@ch2/macro-shell/displayUi";
import "@ch2/macro-shell/headerToolbar.css";
import "./index.css";

applyColorScheme(readStoredColorScheme());

const qc = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <ProductWall>
        <StatsGlossaryPresentationProvider component={RentStatsGlossaryHelp}>
        <App />
        </StatsGlossaryPresentationProvider>
      </ProductWall>
    </QueryClientProvider>
  </React.StrictMode>,
);
