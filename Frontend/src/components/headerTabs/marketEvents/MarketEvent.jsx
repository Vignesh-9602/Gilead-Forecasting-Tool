import React, { useState, useEffect, useContext } from "react";
import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    Button,
} from "@mui/material";

import { GlobalContext } from "../../../context/Provider";
import { getScenarioFilters } from "../../../services/apiService";

export default function MarketEvents() {
    const { favState } = useContext(GlobalContext);

    const therapyArea = favState?.selectedTherapyArea;

    const [indication, setIndication] = useState("");
    const [lot, setLot] = useState("");

    const [selectedScenario, setSelectedScenario] = useState("Aggressive Entry");
    const [mappingData, setMappingData] = useState({});
    const [filterOptions, setFilterOptions] = useState({
        indications: [],
    });

    useEffect(() => {
        if (therapyArea) {
            fetchFilters();
        }
    }, [therapyArea]);

    const fetchFilters = async () => {
        try {
            const response = await getScenarioFilters(therapyArea);

            const resData = response?.data;

            setMappingData(resData?.data || {});

            setFilterOptions({
                indications: Object.keys(resData?.data || {}),
            });

        } catch (error) {
            console.error("Failed to fetch filters", error);
        }
    };

    const availableLots = indication
        ? Object.keys(mappingData[indication] || {})
        : [];

    const handleApplyFilter = () => {
        const payload = {
            ta_name: therapyArea,
            indication,
            lot,
        };

        console.log("Market Event Payload:", payload);

        // future API call here
    };

    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "180px",
        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
        },
    };

    return (
        <Box sx={{ p: 3 }}>
            <Paper
                sx={{
                    p: 3,
                    borderRadius: "16px",
                    border: "1px solid #D8DEE8",
                    boxShadow: "none",
                }}
            >
                <Box
                    sx={{
                        display: "flex",
                        gap: 3,
                        flexWrap: "wrap",
                        alignItems: "end",
                    }}
                >
                    {/* Therapeutic Area */}
                    <Box>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "14px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
                            THERAPEUTIC AREA
                        </Typography>

                        <Box
                            sx={{
                                height: 35,
                                px: 2,
                                display: "flex",
                                alignItems: "center",
                                gap: 1,
                                border: "1px solid #D8DEE8",
                                borderRadius: "8px",
                                backgroundColor: "#d7dde6",
                                minWidth: "140px",
                            }}
                        >
                            <Box
                                sx={{
                                    width: 8,
                                    height: 8,
                                    borderRadius: "50%",
                                    backgroundColor: "#22c55e",
                                }}
                            />

                            <Typography>
                                {therapyArea}
                            </Typography>
                        </Box>
                    </Box>

                    {/* Indication */}
                    <Box>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "14px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
                            INDICATION
                        </Typography>

                        <FormControl sx={inputStyle}>
                            <Select
                                value={indication}
                                onChange={(e) => {
                                    setIndication(e.target.value);
                                    setLot("");
                                }}
                                displayEmpty
                            >
                                <MenuItem value="" disabled>
                                    Select Indication
                                </MenuItem>

                                {filterOptions.indications.map((item) => (
                                    <MenuItem
                                        key={item}
                                        value={item}
                                    >
                                        {item}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* LOT */}
                    <Box>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "14px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
                            LOT
                        </Typography>

                        <FormControl sx={inputStyle}>
                            <Select
                                value={lot}
                                onChange={(e) =>
                                    setLot(e.target.value)
                                }
                                displayEmpty
                            >
                                <MenuItem value="" disabled>
                                    Select LOT
                                </MenuItem>

                                {availableLots.map((item) => (
                                    <MenuItem
                                        key={item}
                                        value={item}
                                    >
                                        {item}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* Apply Filter */}
                    <Box sx={{ ml: 2 }}>
                        <Button
                            variant="contained"
                            onClick={handleApplyFilter}
                            sx={{
                                textTransform: "none",
                                borderRadius: "8px",
                                backgroundColor: "#4F46E5",
                                height: "35px",
                            }}
                        >
                            Apply Filter
                        </Button>
                    </Box>
                </Box>
                <Paper
                    sx={{
                        mt: 3,
                        px: 3,
                        py: 2,
                        borderRadius: "12px",
                        border: "1px solid #D8DEE8",
                        boxShadow: "none",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        flexWrap: "wrap",
                        gap: 2,
                    }}
                >
                    {/* Left Section */}
                    <Box
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 2,
                            flexWrap: "wrap",
                        }}
                    >
                        {/* Title */}
                        <Typography
                            sx={{
                                fontSize: "18px",
                                fontWeight: 700,
                                color: "#475569",
                                textTransform: "uppercase",
                            }}
                        >
                            Impact Curve Configuration
                        </Typography>

                        {/* Scenario Selector Label */}
                        <Typography
                            sx={{
                                fontSize: "14px",
                                fontWeight: 600,
                                color: "#64748b",
                            }}
                        >
                            Scenario selector:
                        </Typography>

                        {/* Scenario Selector */}
                        <FormControl
                            size="small"
                            sx={{
                                minWidth: 180,
                                "& .MuiOutlinedInput-root": {
                                    height: "36px",
                                    borderRadius: "8px",
                                    backgroundColor: "#fff",
                                },
                            }}
                        >
                            <Select
                                value={selectedScenario}
                                onChange={(e) =>
                                    setSelectedScenario(e.target.value)
                                }
                            >
                                <MenuItem value="Aggressive Entry">
                                    Aggressive Entry
                                </MenuItem>

                                <MenuItem value="Conservative Entry">
                                    Conservative Entry
                                </MenuItem>

                                <MenuItem value="Delayed Launch">
                                    Delayed Launch
                                </MenuItem>
                            </Select>
                        </FormControl>

                        {/* Run Calculation Button */}
                        <Button
                            variant="contained"
                            sx={{
                                height: "36px",
                                textTransform: "none",
                                borderRadius: "8px",
                                backgroundColor: "#4F46E5",
                                px: 3,
                                fontWeight: 600,
                            }}
                        >
                            Run Calculation
                        </Button>
                    </Box>

                    {/* Right Section */}
                    <Button
                        variant="contained"
                        sx={{
                            height: "36px",
                            textTransform: "none",
                            borderRadius: "8px",
                            backgroundColor: "#4F46E5",
                            px: 2.5,
                            fontWeight: 600,
                            whiteSpace: "nowrap",
                        }}
                    >
                        + Add New Event
                    </Button>
                </Paper>
            </Paper>
        </Box>
    );
}