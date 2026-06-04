import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import BuildingRegressionPage from "./pages/BuildingRegressionPage";
import "./index.css";

const qc = new QueryClient();

function Root() {
  const view = new URLSearchParams(window.location.search).get("view");
  if (view === "regression") return <BuildingRegressionPage />;
  return <App />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <Root />
    </QueryClientProvider>
  </React.StrictMode>,
);
