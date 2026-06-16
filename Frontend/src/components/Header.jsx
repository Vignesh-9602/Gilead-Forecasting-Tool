import React, { useContext } from "react";
import { AppBar, Toolbar, Tabs, Tab, Typography, Box } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { GlobalContext } from "../context/Provider";

export default function Header({ tabs, activeTab, setActiveTab }) {
    const navigate = useNavigate();
    const { favDispatch } = useContext(GlobalContext);

    const handleGoToLanding = () => {
        localStorage.removeItem("selectedTherapyArea");
        localStorage.removeItem("activeTab");
        localStorage.removeItem("pbcActiveTab");

        favDispatch({
            type: "SELECTED_THERAPY_AREA",
            payload: "",
        });

        setActiveTab("Configurations");

        navigate("/landingpage");
    };

    return (
        <AppBar
            position="sticky"
            sx={{
                backgroundColor: "#07142B",
                width: "100%",
                boxShadow: "none",
            }}
        >
            <Toolbar
                sx={{
                    minHeight: "72px",
                    px: "16px !important",
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                }}
            >
                <Typography
                    onClick={handleGoToLanding}
                    sx={{
                        fontWeight: 700,
                        fontSize: "20px",
                        color: "white",
                        mr: 4,
                        whiteSpace: "nowrap",
                        cursor: "pointer",
                        "&:hover": {
                            opacity: 0.9,
                        }
                    }}
                >
                    FORECAST<span style={{ color: "#6E7CFF" }}>PRO</span>
                </Typography>

                <Box sx={{ flexGrow: 1, overflowX: "auto" }}>
                    <Tabs
                        value={activeTab}
                        onChange={(e, newValue) => setActiveTab(newValue)}
                        variant="scrollable"
                        scrollButtons="auto"
                        textColor="inherit"
                        indicatorColor="none"
                        sx={{
                            minHeight: "36px",
                            "& .MuiTabs-flexContainer": {
                                gap: "8px",
                            },
                            "& .MuiTab-root": {
                                color: "#A0A7B5",
                                textTransform: "none",
                                fontSize: "14px",
                                fontWeight: 500,
                                borderRadius: "10px",
                                minHeight: "36px",
                                padding: "4px 12px",
                                whiteSpace: "nowrap",
                            },
                            "& .Mui-selected": {
                                backgroundColor: "#4F46E5",
                                color: "#fff !important",
                                minHeight: "36px",
                                padding: "4px 12px",
                            },
                        }}
                    >
                        {tabs.map((tab) => (
                            <Tab key={tab} label={tab} value={tab} />
                        ))}
                    </Tabs>
                </Box>
            </Toolbar>
        </AppBar>
    );
}