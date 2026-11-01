import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { applyColorScheme, readStoredColorScheme } from "@ch2/macro-shell/displayUi";
import { ProductAccessProvider } from "@ch2/macro-shell/productAccess";
import { StatsGlossaryPresentationProvider } from "@ch2/stats-glossary";
import StatsGlossaryHelp from "./components/StatsGlossaryHelp";
import App from "./App";
import "./index.css";

applyColorScheme(readStoredColorScheme());

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000 } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ProductAccessProvider>
        <StatsGlossaryPresentationProvider component={StatsGlossaryHelp}>
          <App />
        </StatsGlossaryPresentationProvider>
      </ProductAccessProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
