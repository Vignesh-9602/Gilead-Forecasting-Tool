import React from "react";
import AppRoutes from "./routes/AppRoutes";
import { GlobalProvider } from "./context/Provider";

export default function App() {
  return (
    <GlobalProvider>
      <AppRoutes />
    </GlobalProvider>
  );
}