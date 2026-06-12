import React, { useState, useEffect } from "react";
import { Box } from "@mui/material";
import Header from "../components/Header";
import GlobalConfiguration from "../components/headerTabs/GlobalConfigurations";
import SnackbarNotification from "../components/snackBar/SnackBar";
import ModelInput from "../components/headerTabs/ModelInput";
import Scenarios from "../components/headerTabs/scenario/Scenarios";
import MarketEvents from "../components/headerTabs/marketEvents/MarketEvent";
import VialCalculator from "../components/headerTabs/vialCalculator/VialCalculator";
import Output from "../components/headerTabs/output/Output";
import NetDemandRevenue from "../components/headerTabs/netDemandRevenue/NetDemandRevenue";

const tabs = [
    "Configurations",
    "Model Inputs",
    "Scenarios",
    "Market Events",
    "Vial Calculator",
    "Net Demand Revenue",
    "Output",
    "Monte Carlo Simulation",
];

export default function MainLayout() {
    // const [activeTab, setActiveTab] = useState("Configurations");
    const [activeTab, setActiveTab] = useState(
        localStorage.getItem("activeTab") || "Configurations"
    );

    useEffect(() => {
        localStorage.setItem("activeTab", activeTab);
    }, [activeTab]);

    const renderContent = () => {
        switch (activeTab) {
            case "Configurations":
                return <GlobalConfiguration />;
            case "Model Inputs":
                return <ModelInput />;
            case "Scenarios":
                return <Scenarios />;
            case "Market Events":
                return <MarketEvents />;
            case "Vial Calculator":
                return <VialCalculator />;
            case "Net Demand Revenue":
                return <NetDemandRevenue />;
            // case "Output":
            //     return <Output />;
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