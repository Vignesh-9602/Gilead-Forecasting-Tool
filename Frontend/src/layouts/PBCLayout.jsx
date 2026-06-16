import React, { useState, useEffect } from "react";
import { Box } from "@mui/material";
import Header from "../components/Header";
import SnackbarNotification from "../components/snackBar/SnackBar";
import PBCGlobalConfigurations from "../components/pbc/GlobalConfigurations";

const tabs = [
    "Configurations",
    "Model Inputs",
    "Market Events",
    "Output",
];

export default function PBCLayout() {
    const [activeTab, setActiveTab] = useState(
        localStorage.getItem("pbcActiveTab") || "Configurations"
    );

    useEffect(() => {
        localStorage.setItem("pbcActiveTab", activeTab);
    }, [activeTab]);

    const renderContent = () => {
        switch (activeTab) {
            case "Configurations":
                return <PBCGlobalConfigurations />;

            default:
                return (
                    <Box p={3}>
                        <h2>{activeTab}</h2>
                        <p>PBC component coming soon...</p>
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