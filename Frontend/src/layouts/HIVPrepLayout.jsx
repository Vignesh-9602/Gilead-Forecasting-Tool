import React, { useState, useEffect } from "react";
import { Box } from "@mui/material";
import Header from "../components/Header";
import SnackbarNotification from "../components/snackBar/SnackBar";
import HIVPrepGlobalConfigurations from "../components/hivPrep/globalConfigurations/HIVPrepGlobalConfigurations";
import HIVPrepModelInput from "../components/hivPrep/modelInputs/HIVPrepModelInputs";
import HIVPrepMarketEvent from "../components/hivPrep/marketEvents/HIVPrepMarketEvent";
import HIVPrepOutput from "../components/hivPrep/output/HIVPrepOutput";

const tabs = [
    "Configurations",
    "Model Inputs",
    "Market Events",
    "Output",
];

export default function HIVPrepLayout() {
    const [activeTab, setActiveTab] = useState(
        localStorage.getItem("hivPrepActiveTab") || "Configurations"
    );

    useEffect(() => {
        localStorage.setItem("hivPrepActiveTab", activeTab);
    }, [activeTab]);

    const renderContent = () => {
        switch (activeTab) {
            case "Configurations":
                return <HIVPrepGlobalConfigurations />;

            case "Model Inputs":
                return <HIVPrepModelInput />;

            case "Market Events":
                return <HIVPrepMarketEvent />;

            case "Output":
                return <HIVPrepOutput />;

            default:
                return (
                    <Box p={3}>
                        <h2>{activeTab}</h2>
                        <p>HIV component coming soon...</p>
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