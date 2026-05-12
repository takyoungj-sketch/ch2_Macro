import { Route, Routes } from "react-router-dom";
import Dashboard from "./Dashboard";
import ComparePage from "./pages/ComparePage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/compare" element={<ComparePage />} />
    </Routes>
  );
}
