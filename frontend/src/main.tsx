import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { applyColorScheme, readStoredColorScheme } from "@ch2/macro-shell/displayUi";
import { ProductAccessProvider } from "@ch2/macro-shell/productAccess";
import App from "./App";
import MobileLandApp from "./MobileLandApp";
import { useMobileScreen } from "@ch2/macro-shell/mobile/useMobileScreen";
import "./index.css";

applyColorScheme(readStoredColorScheme());

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000 } },
});

function Root() {
  return useMobileScreen() ? <MobileLandApp /> : <App />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ProductAccessProvider>
        <Root />
      </ProductAccessProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
