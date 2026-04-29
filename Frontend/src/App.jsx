import React from "react";
import AppRoutes from "./routes/AppRoutes";
import { GlobalProvider } from "./context/Provider";
import GlobalLoader from "./components/globalLoader/GlobalLoader";

export default function App() {
  return (
    <GlobalProvider>
      <GlobalLoader />
      <AppRoutes />
    </GlobalProvider>
  );
}