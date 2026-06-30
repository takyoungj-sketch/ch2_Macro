import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { applyColorScheme, readStoredColorScheme } from "@ch2/macro-shell/displayUi";
import App from "./App";
import "./index.css";

applyColorScheme(readStoredColorScheme());

const qc = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
