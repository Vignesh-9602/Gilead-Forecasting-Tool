import React, { useState, useEffect } from "react";
import { Box } from "@mui/material";
import Header from "../components/Header";
import SnackbarNotification from "../components/snackBar/SnackBar";
// import PBCModelInput from "../components/hcv/ModelInput/ModelInput";
import HIVGlobalConfigurations from "../components/hiv/globalConfigurations/HIVGlobalConfigurations";
import HIVModelInput from "../components/hiv/modelInputs/HIVModelInputs";

const tabs = [
    "Configurations",
    "Model Inputs",
    "Market Events",
    "Output",
];

export default function HIVLayout() {
    const [activeTab, setActiveTab] = useState(
        localStorage.getItem("hivActiveTab") || "Configurations"
    );

    useEffect(() => {
        localStorage.setItem("hivActiveTab", activeTab);
    }, [activeTab]);

    const renderContent = () => {
        switch (activeTab) {
            case "Configurations":
                return <HIVGlobalConfigurations />;

            case "Model Inputs":
                return <HIVModelInput />;

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