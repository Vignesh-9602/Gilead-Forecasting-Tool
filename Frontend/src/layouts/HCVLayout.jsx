import React, { useState, useEffect } from "react";
import { Box } from "@mui/material";
import Header from "../components/Header";
import SnackbarNotification from "../components/snackBar/SnackBar";
import PBCGlobalConfigurations from "../components/pbc/GlobalConfiguration/GlobalConfigurations";
import PBCModelInput from "../components/pbc/ModelInput/ModelInput";

const tabs = [
    "Configurations",
    "Model Inputs",
    "Market Events",
    "Output",
];

export default function HCVLayout() {
    const [activeTab, setActiveTab] = useState(
        localStorage.getItem("pbcActiveTab") || "Configurations"
    );

    useEffect(() => {
        localStorage.setItem("hcvActiveTab", activeTab);
    }, [activeTab]);

    const renderContent = () => {
        switch (activeTab) {
            case "Configurations":
                return <PBCGlobalConfigurations />;

            case "Model Inputs":
                return <PBCModelInput />;

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