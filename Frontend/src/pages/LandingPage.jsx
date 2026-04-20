import React, { useEffect, useState, useContext } from "react";
import {
    Box,
    Card,
    CardActionArea,
    Typography,
    CircularProgress,
} from "@mui/material";

import { getTherapyAreaList } from "../services/apiService";
import { useNavigate } from "react-router-dom";
import { GlobalContext } from "../context/Provider";

export default function LandingPage() {
    const [therapyAreas, setTherapyAreas] = useState([]);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();
    const { favDispatch } = useContext(GlobalContext);

    useEffect(() => {
        fetchTherapyAreas();
    }, []);

    const fetchTherapyAreas = async () => {
        try {
            const response = await getTherapyAreaList();
            setTherapyAreas(response?.data?.ta_list || []);
        } catch (error) {
            console.error("Failed to fetch therapy areas", error);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <Box
                sx={{
                    height: "100vh",
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                }}
            >
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box data-testid="login-form"
            sx={{
                minHeight: "100vh",
                display: "flex",
                flexDirection: "column",
                backgroundColor: "#f5f7fa",
            }}
        >
            {/* HEADER */}
            <Box
                sx={{
                    height: "65px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "linear-gradient(90deg, #0A2342, #1e3a5f)",
                    color: "white",
                    fontWeight: 700,
                    fontSize: "22px",
                    letterSpacing: 1,
                }}
            >
                FORECAST<span style={{ color: "#7c8cff" }}>PRO</span>
            </Box>

            {/*  MAIN CONTENT */}
            <Box
                sx={{
                    flex: 1,
                    textAlign: "center",
                    mt: 8,
                    px: 3,
                }}
            >
                {/* Title */}
                <Typography
                    sx={{
                        fontSize: "36px",
                        fontWeight: 800,
                        color: "#0f172a",
                    }}
                >
                    Select Therapeutic Area
                </Typography>

                {/* Subtitle */}
                <Typography
                    sx={{
                        fontSize: "18px",
                        color: "#64748b",
                        mt: 1,
                        mb: 8,
                    }}
                >
                    Choose a module to begin your market forecast analysis
                </Typography>

                {/* Cards */}
                <Box
                    sx={{
                        display: "flex",
                        gap: 4,
                        flexWrap: "wrap",
                        justifyContent: "center",
                    }}
                >
                    {therapyAreas.map((item, index) => (
                        <Card
                            key={index}
                            sx={{
                                width: 260,
                                height: 180,
                                borderRadius: "16px",
                                border: "1px solid #e2e8f0",
                                boxShadow: "0 4px 12px rgba(0,0,0,0.05)",
                                transition: "0.3s",
                                "&:hover": {
                                    transform: "translateY(-6px)",
                                    boxShadow: "0 8px 20px rgba(0,0,0,0.1)",
                                },
                            }}
                        >
                            <CardActionArea
                                sx={{ height: "100%" }}
                                onClick={() => {
                                    favDispatch({
                                        type: "SELECTED_THERAPY_AREA",
                                        payload: item,
                                    });

                                    localStorage.setItem("activeTab", "Configurations");
                                    navigate("/app");
                                }}
                            >
                                <Box
                                    sx={{
                                        height: "100%",
                                        display: "flex",
                                        flexDirection: "column",
                                        justifyContent: "center",
                                        alignItems: "center",
                                        gap: 2,
                                    }}
                                >
                                    <Typography
                                        sx={{
                                            fontSize: "32px",
                                            fontWeight: 700,
                                            color: "#0A2342",
                                        }}
                                    >
                                        {item}
                                    </Typography>

                                    {/* <Box
                                        sx={{
                                            px: 3,
                                            py: 1,
                                            borderRadius: "8px",
                                            border: "1px solid #cbd5f5",
                                            color: "#4f46e5",
                                            fontSize: "14px",
                                            fontWeight: 600,
                                        }}
                                    >
                                        Enter Module
                                    </Box> */}
                                </Box>
                            </CardActionArea>
                        </Card>
                    ))}
                </Box>
            </Box>

            {/* FOOTER (always bottom) */}
            <Box
                sx={{
                    textAlign: "center",
                    py: 2,
                    borderTop: "1px solid #e2e8f0",
                    backgroundColor: "#f8fafc",
                }}
            >
                <Typography
                    sx={{
                        fontSize: "13px",
                        color: "#64748b",
                    }}
                >
                    © 2026 Forecaster Pro Analytical Systems. All rights reserved.
                </Typography>
            </Box>
        </Box>
    );
}