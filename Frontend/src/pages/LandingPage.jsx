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
        <Box
            sx={{
                minHeight: "100vh",
                backgroundColor: "#f5f7fa",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                px: 3,
                py: 6,
            }}
        >
            {/* Greeting */}
            <Typography
                sx={{
                    fontSize: "32px",
                    fontWeight: 700,
                    color: "#0A2342",
                    mb: 1,
                }}
            >
                Gilead Forecasting Tool
            </Typography>

            {/* Subtitle */}
            <Typography
                sx={{
                    fontSize: "18px",
                    color: "#5B708B",
                    mb: 4,
                    mt: 10
                }}
            >
                Select Therapeutic Area to Proceed
            </Typography>

            {/* Image */}
            {/* <Box
                component="img"
                src="https://images.unsplash.com/photo-1576091160550-2173dba999ef"
                alt="ePharma"
                sx={{
                    width: "100%",
                    maxWidth: "520px",
                    height: "240px",
                    objectFit: "cover",
                    borderRadius: "20px",
                    mb: 5,
                    boxShadow: 3,
                }}
            /> */}

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
                            width: 220,
                            height: 140,
                            borderRadius: "16px",
                            boxShadow: 3,
                            transition: "0.3s",
                            "&:hover": {
                                transform: "translateY(-6px)",
                                boxShadow: 6,
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
                                    justifyContent: "center",
                                    alignItems: "center",
                                }}
                            >
                                <Typography
                                    sx={{
                                        fontSize: "22px",
                                        fontWeight: 700,
                                        color: "#0A2342",
                                    }}
                                >
                                    {item}
                                </Typography>
                            </Box>
                        </CardActionArea>
                    </Card>
                ))}
            </Box>
        </Box>
    );
}