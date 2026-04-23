import React, { useState, useEffect, useContext } from "react";
import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    Button,
    Checkbox,
    ListItemText,
} from "@mui/material";

import { GlobalContext } from "../../../context/Provider";
import { getMetricFilters } from "../../../services/apiService";
import ScenarioChart from "./ScenarioChart";
import ScenarioTable from "./ScenarioTable";

const scenarioOptions = [
    "Base Case",
    "Optimized Case",
    "ETS",
    "Bear Case",
];

export default function Scenarios() {
    const { favState } = useContext(GlobalContext);
    const therapyArea = favState?.selectedTherapyArea;

    const [indication, setIndication] = useState("");
    const [lot, setLot] = useState("");
    const [metric, setMetric] = useState("");
    const [compareScenarios, setCompareScenarios] = useState([]);

    const [mappingData, setMappingData] = useState({});
    const [filterOptions, setFilterOptions] = useState({
        indications: [],
        metric_filters: [],
    });

    const [chartData, setChartData] = useState({
        months: [
            "2024-04-01", "2024-05-01", "2024-06-01", "2024-07-01", "2024-08-01",
            "2024-09-01", "2024-10-01", "2024-11-01", "2024-12-01", "2025-01-01",
            "2025-02-01", "2025-03-01", "2025-04-01", "2025-05-01", "2025-06-01",
            "2025-07-01", "2025-08-01", "2025-09-01", "2025-10-01", "2025-11-01",
            "2025-12-01", "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"
        ],
        train_values: [
            392, 761, 647, 769, 740, 512, 526, 775, 496, 531,
            674, 525, 623, 657, 610, 319, 777, 405, 628, 502, 791, 631
        ],
        forecast_start_index: 22,
        scenario_values: {
            "Optimized Case (Actual)": [664, 700, 735],
            "ETS (Actual)": [664, 690, 720],
            "Bear Case (Actual)": [664, 650, 680],
        },
    });

    const [tableData, setTableData] = useState([
        {
            scenario: "Base Case",
            total: [392, 761, 647, 769, 740, 512, 526, 775, 496, 531, 674, 525, 623, 657, 610, 319, 777, 405, 628, 502, 791, 631, 664, 700, 735],
            children: [
                {
                    label: "Trodelvy",
                    values: [196, 380, 323, 384, 370, 256, 263, 387, 248, 265, 337, 262, 311, 328, 305, 159, 388, 202, 314, 251, 395, 315, 332, 350, 367],
                },
                {
                    label: "Trodelvy Combo",
                    values: [196, 381, 324, 385, 370, 256, 263, 388, 248, 266, 337, 263, 312, 329, 305, 160, 389, 203, 314, 251, 396, 316, 332, 350, 368],
                },
            ],
        },
        {
            scenario: "Optimized Case",
            total: [392, 761, 647, 769, 740, 512, 526, 775, 496, 531, 674, 525, 623, 657, 610, 319, 777, 405, 628, 502, 791, 631, 664, 700, 735],
            children: [
                {
                    label: "TPC",
                    values: [196, 380, 323, 384, 370, 256, 263, 387, 248, 265, 337, 262, 311, 328, 305, 159, 388, 202, 314, 251, 395, 315, 332, 350, 367],
                },
                {
                    label: "Trodelvy",
                    values: [196, 381, 324, 385, 370, 256, 263, 388, 248, 266, 337, 263, 312, 329, 305, 160, 389, 203, 314, 251, 396, 316, 332, 350, 368],
                },
            ],
        },
    ]);

    useEffect(() => {
        if (therapyArea) {
            fetchMetricFilters();
        }
    }, [therapyArea]);

    const fetchMetricFilters = async () => {
        try {
            const response = await getMetricFilters(therapyArea);
            const resData = response?.data;

            setMappingData(resData?.data || {});

            setFilterOptions({
                indications: Object.keys(resData?.data || {}),
                metric_filters: resData?.metric_filters || [],
            });
        } catch (error) {
            console.error("Failed to fetch metric filters", error);
        }
    };

    const availableLots = indication
        ? Object.keys(mappingData[indication] || {})
        : [];

    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "160px",
        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
        },
    };

    const handleApply = () => {
        console.log({
            therapyArea,
            indication,
            lot,
            metric,
            compareScenarios,
        });
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
                        <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
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
                                minWidth: "120px",
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
                            <Typography>{therapyArea}</Typography>
                        </Box>
                    </Box>

                    {/* Indication */}
                    <Box>
                        <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
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
                                <MenuItem value="" disabled>Select Indication</MenuItem>
                                {filterOptions.indications.map((item) => (
                                    <MenuItem key={item} value={item}>
                                        {item}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* LOT */}
                    <Box>
                        <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                            LOT
                        </Typography>

                        <FormControl sx={inputStyle}>
                            <Select
                                value={lot}
                                onChange={(e) => setLot(e.target.value)}
                                displayEmpty
                            >
                                <MenuItem value="" disabled>Select LOT</MenuItem>
                                {availableLots.map((item) => (
                                    <MenuItem key={item} value={item}>
                                        {item}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* Metric */}
                    <Box>
                        <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                            METRIC
                        </Typography>

                        <FormControl sx={inputStyle}>
                            <Select
                                value={metric}
                                onChange={(e) => setMetric(e.target.value)}
                                displayEmpty
                            >
                                <MenuItem value="" disabled>Select Metric</MenuItem>
                                {filterOptions.metric_filters.map((item) => (
                                    <MenuItem key={item.value} value={item.value}>
                                        {item.label}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* Compare Scenarios */}
                    <Box>
                        <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                            COMPARE SCENARIOS
                        </Typography>

                        <FormControl sx={{ ...inputStyle, minWidth: 220 }}>
                            <Select
                                multiple
                                value={compareScenarios}
                                onChange={(e) => setCompareScenarios(e.target.value)}
                                renderValue={(selected) => selected.join(", ")}
                            >
                                {scenarioOptions.map((name) => (
                                    <MenuItem key={name} value={name}>
                                        <Checkbox checked={compareScenarios.includes(name)} />
                                        <ListItemText primary={name} />
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* Gap = 3 */}
                    <Box sx={{ ml: 3 }}>
                        <Button
                            variant="contained"
                            onClick={handleApply}
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
                        px: 4,
                        py: 2,
                        borderRadius: "14px",
                        border: "1px solid #D8DEE8",
                        boxShadow: "none",
                        backgroundColor: "#f8fafc",
                    }}
                >
                    <Box
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                            flexWrap: "wrap",
                        }}
                    >
                        {/* Label */}
                        <Typography
                            sx={{
                                fontSize: "16px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
                            FINALIZATION STATUS:
                        </Typography>

                        {/* 1L */}
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                            <Box
                                sx={{
                                    width: 12,
                                    height: 12,
                                    borderRadius: "50%",
                                    backgroundColor: "#f59e0b",
                                }}
                            />
                            <Typography sx={{ fontSize: "16px", fontWeight: 600 }}>
                                1L: Pending
                            </Typography>
                        </Box>

                        {/* 2L */}
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                            <Box
                                sx={{
                                    width: 12,
                                    height: 12,
                                    borderRadius: "50%",
                                    backgroundColor: "#10b981",
                                }}
                            />
                            <Typography
                                sx={{
                                    fontSize: "16px",
                                    fontWeight: 700,
                                    color: "#10b981",
                                }}
                            >
                                2L: Optimized Case
                            </Typography>
                        </Box>

                        {/* 3L */}
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                            <Box
                                sx={{
                                    width: 12,
                                    height: 12,
                                    borderRadius: "50%",
                                    backgroundColor: "#f59e0b",
                                }}
                            />
                            <Typography sx={{ fontSize: "16px", fontWeight: 600 }}>
                                3L: Pending
                            </Typography>
                        </Box>
                    </Box>
                </Paper>
                <ScenarioChart chartData={chartData} />
                <ScenarioTable chartData={chartData} tableData={tableData} selectedLot={lot} />
                <Box
                    sx={{
                        display: "flex",
                        justifyContent: "center",
                        mt: 4,
                    }}
                >
                    <Button
                        variant="contained"
                        disabled
                        // disabled={
                        //     !["1L", "2L", "3L+"].every((lotKey) => savedSelections[lotKey])
                        // }
                        sx={{
                            minWidth: "220px",
                            height: "42px",
                            borderRadius: "10px",
                            textTransform: "none",
                            backgroundColor: "#0f172a",
                        }}
                    >
                        Finalize All Scenarios
                    </Button>
                </Box>
            </Paper>
        </Box>
    );
}