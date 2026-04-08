import React, { useState } from "react";
import { Box } from "@mui/material";
import Header from "./components/Header";
import GlobalConfiguration from "./components/headerTabs/GlobalConfigurations";
import SnackbarNotification from "./components/snackBar/SnackBar";

const tabs = [
  "Configurations",
  "Model Inputs",
  "Scenarios",
  "Market Events",
  "Vial Calculator",
  "Pricing & WAC",
  "Output",
  "Monte Carlo Simulation",
];

export default function App() {
  const [activeTab, setActiveTab] = useState("Configurations");

  const renderContent = () => {
    switch (activeTab) {
      case "Configurations":
        return <GlobalConfiguration />;
      default:
        return (
          <Box p={3}>
            <h2>{activeTab}</h2>
            <p>Future component will come here...</p>
          </Box>
        );
    }
  };

  return (
    <Box sx={{ width: "100%", height: "100vh", overflow: "hidden" }}>
      <Header
        tabs={tabs}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      <SnackbarNotification />

      <Box
        sx={{
          height: "calc(100vh - 72px)",
          overflowY: "auto",
          width: "100%",
          backgroundColor: "#f5f5f5",
        }}
      >
        {renderContent()}
      </Box>
    </Box>
  );
}