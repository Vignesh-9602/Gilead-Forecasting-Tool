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
import { getScenarioFilters, applyScenarioFilters } from "../../../services/apiService";
import ScenarioChart from "./ScenarioChart";
import ScenarioTable from "./ScenarioTable";

// const scenarioOptions = [
//     "Base Case",
//     "Optimized Case",
//     "ETS",
//     "Bear Case",
// ];

export default function Scenarios() {
    const { favState } = useContext(GlobalContext);
    const therapyArea = favState?.selectedTherapyArea;

    const [indication, setIndication] = useState("");
    const [lot, setLot] = useState("");
    const [metric, setMetric] = useState("");
    const [brand, setBrand] = useState("");
    const [compareScenarios, setCompareScenarios] = useState([]);

    const [mappingData, setMappingData] = useState({});
    const [filterOptions, setFilterOptions] = useState({
        indications: [],
        metric_filters: [],
    });

    const [chartData, setChartData] = useState(null);
    const [tableData, setTableData] = useState([]);

    useEffect(() => {
        if (therapyArea) {
            fetchScenarioFilters();
        }
    }, [therapyArea]);

    useEffect(() => {
        setChartData(null);
        setTableData([]);
    }, [indication, lot, metric]);
    

    const fetchScenarioFilters = async () => {
        try {
            const response = await getScenarioFilters(therapyArea);
            const resData = response?.data;

            // full mapping
            setMappingData(resData?.data || {});

            // indications (top-level keys)
            setFilterOptions({
                indications: Object.keys(resData?.data || {}),
                metric_filters: resData?.metric_filters || [],
            });

        } catch (error) {
            console.error("Failed to fetch scenario filters", error);
        }
    };

    const handleApply = async () => {
        if (!therapyArea || !indication || !lot || !metric) return;

        const payload = {
            ta_name: therapyArea,
            indication,
            lot,
            metric,
            scenario_names: availableScenarios
                .filter(sc => compareScenarios.includes(sc.scenario_id))
                .map(sc => sc.scenario_name),
            product: metric === "market_share" ? brand : ""
        };

        try {
            const response = await applyScenarioFilters(payload);
            const data = response?.data;

            // DIRECT ASSIGN (no transformation needed)
            setChartData(data.chart);
            setTableData(data.table);

        } catch (error) {
            console.error("Apply filter failed", error);
        }
    };

    const availableLots = indication
        ? Object.keys(mappingData[indication] || {})
        : [];

    const availableProducts =
        indication && lot
            ? mappingData[indication]?.[lot]?.products || []
            : [];

    const availableScenarios =
        indication && lot
            ? mappingData[indication]?.[lot]?.available_scenarios || []
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

    // const handleApply = () => {
    //     console.log({
    //         therapyArea,
    //         indication,
    //         lot,
    //         metric,
    //         compareScenarios,
    //     });
    // };

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
                                    setCompareScenarios([]);
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
                                onChange={(e) => {
                                    setLot(e.target.value)
                                    setBrand("");
                                    setCompareScenarios([]);
                                }}
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
                                onChange={(e) => {
                                    setMetric(e.target.value);
                                    setBrand("");
                                }}
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

                    <Box>
                        <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                            PRODUCT
                        </Typography>

                        <FormControl sx={inputStyle}>
                            <Select
                                value={brand}
                                onChange={(e) => setBrand(e.target.value)}
                                disabled={metric !== "market_share" || !lot}
                                displayEmpty
                            >
                                <MenuItem value="" disabled>Select Product</MenuItem>

                                {availableProducts.map((item) => (
                                    <MenuItem key={item} value={item}>
                                        {item}
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
                                {availableScenarios.map((sc) => (
                                    <MenuItem key={sc.scenario_id} value={sc.scenario_id}>
                                        <Checkbox checked={compareScenarios.includes(sc.scenario_id)} />
                                        <ListItemText primary={sc.scenario_name} />
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
            </Paper >
        </Box >
    );
}