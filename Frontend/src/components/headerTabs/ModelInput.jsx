import React, { useState, useEffect, useContext } from "react";
import { Box, Paper, Typography, FormControl, Select, MenuItem, TextField, Button, Divider, } from "@mui/material";
import Slider from "@mui/material/Slider";
import { GlobalContext } from "../../context/Provider";
import ForecastTrendChart from "./ForecastTrendChart";
import { getMetricFilters, applyMetricFilters, recalculateMetrics, saveScenario } from "../../services/apiService";

export default function ModelInput() {
    const [indication, setIndication] = useState("");
    const [lot, setLot] = useState("");
    const [metric, setMetric] = useState("");
    const [brand, setBrand] = useState("");
    const [scenarioName, setScenarioName] = useState("");
    const [editable, setEditable] = useState(false);

    const [modelSelection, setModelSelection] = useState("ets");

    const [growthType, setGrowthType] = useState("linear");
    const [totalGrowth, setTotalGrowth] = useState(10);
    const [duration, setDuration] = useState(12);

    const [multiplier, setMultiplier] = useState(1.0);
    const [alpha, setAlpha] = useState(0);
    const [beta, setBeta] = useState(0);
    const [gamma, setGamma] = useState(0);

    const [trendType, setTrendType] = useState("");
    const [seasonality, setSeasonality] = useState("None");

    const [mappingData, setMappingData] = useState({});
    const [filterOptions, setFilterOptions] = useState({
        indications: [],
        metric_filters: [],
    });

    const [chartData, setChartData] = useState(null);
    const [tableData, setTableData] = useState([]);

    const [etsFactors, setEtsFactors] = useState({});
    const [trajectoryFactors, setTrajectoryFactors] = useState({});

    const [showTrajectory, setShowTrajectory] = useState(false);
    const [trajectoryStart, setTrajectoryStart] = useState("");

    const { favState } = useContext(GlobalContext);
    const therapyArea = favState?.selectedTherapyArea;

    useEffect(() => {
        if (therapyArea) {
            fetchMetricFilters();
        }
    }, [therapyArea]);

    useEffect(() => {
        setAlpha(etsFactors?.alpha ?? 0);
        setBeta(etsFactors?.beta ?? 0);
        setGamma(etsFactors?.gamma ?? 0);
        setTrendType(etsFactors?.trend_type || "");

        setGrowthType(trajectoryFactors?.growth_type || "linear");
        setTotalGrowth(trajectoryFactors?.total_growth ?? 0);
        setDuration(trajectoryFactors?.duration ?? 12);
        setTrajectoryStart(trajectoryFactors?.trajectory_start || "");
    }, [etsFactors, trajectoryFactors]);

    const fetchMetricFilters = async () => {
        try {
            const response = await getMetricFilters(therapyArea);
            const resData = response?.data;

            setMappingData(resData?.data || {});

            setFilterOptions({
                indications: Object.keys(resData?.data || {}),
                metric_filters: resData?.metric_filters || [],
            });

            // reset
            setIndication("");
            setLot("");
            setMetric("");
            setBrand("");
        } catch (error) {
            console.error("Failed to fetch metric filters", error);
        }
    };

    const handleApplyFilter = async () => {
        const payload = {
            ta_name: therapyArea,
            indications: indication ? [indication] : [],
            lots: lot ? [lot] : [],
            metric_filter: metric,
            product: metric === "market_share" ? brand : "",
        };

        try {
            const response = await applyMetricFilters(payload);
            const data = response?.data;

            const ets = data?.factors?.ets || {};
            const trajectory = data?.factors?.trajectory || {};

            setMultiplier(data?.factors?.multiplier ?? 1);

            setEtsFactors(ets);
            setTrajectoryFactors(trajectory);

            setAlpha(ets?.alpha ?? 0);
            setBeta(ets?.beta ?? 0);
            setGamma(ets?.gamma ?? 0);
            setTrendType(ets?.trend_type || "");

            setGrowthType(trajectory?.growth_type || "linear");
            setTotalGrowth(trajectory?.total_growth ?? 0);
            setDuration(trajectory?.duration ?? 12);

            setTrajectoryStart(
                trajectory?.trajectory_start ||
                data?.chart?.months?.[data?.chart?.forecast_start_index] ||
                ""
            );

            setChartData(data?.chart || null);
            setTableData(data?.table || []);
            setEditable(false);
        } catch (error) {
            console.error("Failed to apply metric filters", error);
        }
    };

    const handleRecalculate = async () => {
        const payload = {
            ta_name: therapyArea,
            indications: indication ? [indication] : [],
            lots: lot ? [lot] : [],
            metric_filter: metric,
            product: metric === "market_share" ? brand : "",
            model_type: showTrajectory ? "trajectory" : "ets",
            factors: {
                multiplier,
                ets: {
                    alpha,
                    beta,
                    gamma,
                    trend_type: trendType,
                    seasonality: seasonality || "none",
                },
                ...(showTrajectory && {
                    trajectory: {
                        growth_type: growthType,
                        total_growth: totalGrowth,
                        duration,
                        trajectory_start: trajectoryStart,
                    },
                }),
            },
        };

        try {
            const response = await recalculateMetrics(payload);
            const data = response?.data;

            const ets = data?.factors?.ets || {};
            const trajectory = data?.factors?.trajectory || {};

            setMultiplier(data?.factors?.multiplier ?? 1);

            setEtsFactors(ets);
            setTrajectoryFactors(trajectory);

            // update chart
            setChartData(data?.chart || null);

            // update table
            setTableData(data?.table || []);

            setEditable(false);
        } catch (error) {
            console.error("Failed to recalculate metrics", error);
        }
    };


    //  Dynamic values
    const availableLots = indication
        ? Object.keys(mappingData[indication] || {})
        : [];

    const availableBrands =
        indication && lot
            ? mappingData[indication]?.[lot] || []
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

    // const trajectoryMonthOptions =
    //     chartData?.months?.slice(chartData?.forecast_start_index) || [];

    const trajectoryMonthOptions =
        chartData?.months?.map((month) =>
            new Date(month).toLocaleDateString("en-US", {
                month: "short",
                year: "2-digit",
            })
        ) || [];

    const handleSaveScenario = async () => {
        if (!scenarioName) {
            alert("Please enter scenario name");
            return;
        }

        if (!chartData || !tableData.length) {
            alert("No data to save");
            return;
        }

        const payload = {
            scenario_name: scenarioName,

            ta_name: therapyArea,
            indication,
            metric,
            product: brand || null,
            lot,
            model_type: modelSelection,

            factors: {
                multiplier,
                ets: {
                    alpha,
                    beta,
                    gamma,
                    trend_type: trendType,
                    seasonality: seasonality || "none"
                },
                trajectory: {
                    growth_type: growthType,
                    total_growth: totalGrowth,
                    duration,
                    trajectory_start: trajectoryStart
                },
                active_model: showTrajectory ? "trajectory" : "ets"
            },

            chart: chartData,

            table: tableData    // always latest
        };

        try {
            const res = await saveScenario(payload);
            console.log("Scenario saved:", res.data);
            alert("Scenario saved successfully!");
            // setScenarioName("")
        } catch (err) {
            console.error("Save scenario failed", err);
            alert("Failed to save scenario");
        }
    };

    return (
        <Box sx={{ p: 3 }}>
            <Paper sx={{ p: 3, borderRadius: "16px", border: "1px solid #D8DEE8", boxShadow: "none", }}>
                <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "end", gap: 3, flexWrap: "wrap" }}>
                    {/* LEFT SIDE */}
                    <Box
                        sx={{ display: "flex", gap: 3, flexWrap: "wrap", alignItems: "end", }}>
                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                                THERAPEUTIC AREA
                            </Typography>
                            <Box sx={{ height: 35, px: 2, display: "flex", alignItems: "center", gap: 1, border: "1px solid #D8DEE8", borderRadius: "8px", backgroundColor: "#d7dde6", minWidth: "120px", }} >
                                <Box sx={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: "#22c55e", }} />
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
                                        setBrand("");
                                    }}
                                    displayEmpty
                                >
                                    <MenuItem value="" disabled>Select Indication</MenuItem>
                                    {filterOptions.indications.map((item) => (
                                        <MenuItem key={item} value={item}>{item}</MenuItem>
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
                                        setLot(e.target.value);
                                        setBrand("");
                                    }}
                                    displayEmpty
                                // disabled={!indication}
                                >
                                    <MenuItem value="" disabled>Select LOT</MenuItem>
                                    {availableLots.map((item) => (
                                        <MenuItem key={item} value={item}>{item}</MenuItem>
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
                                        const val = e.target.value;
                                        setMetric(val);
                                        if (val !== "market_share") setBrand("");
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
                        {/* Brand */}
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
                                    {availableBrands.map((item) => (
                                        <MenuItem key={item} value={item}>{item}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Box>
                        <Button variant="contained" onClick={handleApplyFilter} sx={{ textTransform: "none", borderRadius: "8px", backgroundColor: "#4F46E5", }}>
                            Apply Filter
                        </Button>
                    </Box>

                    {/* <Divider orientation="vertical" flexItem sx={{ mx: 2 }} /> */}

                    {/* RIGHT SIDE */}
                    <Box sx={{ display: "flex", gap: 2, alignItems: "end" }} >
                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                                SCENARIO NAME
                            </Typography>
                            <TextField
                                placeholder="e.g. Adjusted Baseline"
                                value={scenarioName}
                                onChange={(e) => setScenarioName(e.target.value)}
                                sx={{ ...inputStyle, minWidth: "220px" }}
                            />
                        </Box>

                        <Button variant="contained" sx={{ height: "35px", px: 4, borderRadius: "10px", backgroundColor: "#4F46E5", textTransform: "none" }} onClick={handleSaveScenario} >
                            Save Scenario
                        </Button>
                    </Box>
                </Box>

                {/* slider */}
                <Paper
                    sx={{ mt: 3, p: 3, borderRadius: "16px", border: "1px solid #D8DEE8", boxShadow: "none", backgroundColor: editable ? "#fff" : "#eff6ff", }} >
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                        <Typography sx={{ fontSize: "14px", fontWeight: 700, color: "#1d4ed8", textTransform: "uppercase" }} > STATISTICAL PROJECTION ENGINE </Typography>
                        <Box display="flex" gap={2}>
                            <Button
                                variant={showTrajectory ? "contained" : "outlined"}
                                size="small"
                                onClick={() => setShowTrajectory(!showTrajectory)}
                                sx={{
                                    textTransform: "none",
                                    borderRadius: "8px",
                                }}
                            >
                                Trajectory
                            </Button>

                            <Button
                                variant="outlined"
                                size="small"
                                onClick={() => setEditable(!editable)}
                                sx={{
                                    textTransform: "none",
                                    borderRadius: "8px",
                                }}
                            >
                                {editable ? "Lock Factors" : "Edit Factors"}
                            </Button>
                        </Box>
                    </Box>

                    <Box sx={{ display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center" }}>
                        {/* MODEL SELECTION */}
                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}> BASE MODEL </Typography>
                            <FormControl sx={inputStyle}>
                                <Select
                                    value={modelSelection}
                                    onChange={(e) => setModelSelection(e.target.value)}
                                    disabled={!editable}
                                >
                                    <MenuItem value="ets">Exponential Smoothing (ETS)</MenuItem>
                                    {/* <MenuItem value="trajectory">Trajectory</MenuItem> */}
                                </Select>
                            </FormControl>
                            {/* <Box sx={{ height: 35, px: 2, display: "flex", alignItems: "center", gap: 1, border: "1px solid #D8DEE8", borderRadius: "8px", backgroundColor: "#d7dde6", minWidth: "120px", }} >
                                <Box sx={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: "#22c55e", }} />
                                <Typography>Exponential Smoothing(ETS)</Typography>
                            </Box> */}
                        </Box>

                        {/* ETS BLOCK */}
                        {/* {modelSelection === "ets" && ( */}
                        <>
                            {[
                                // { label: "MULTIPLIER", value: multiplier, setValue: setMultiplier, min: 0, max: 3, },
                                { label: "LEVEL (α)", value: alpha, setValue: setAlpha, min: 0, max: 1, },
                                { label: "TREND (β)", value: beta, setValue: setBeta, min: 0, max: 1, },
                                { label: "DAMPING (φ)", value: gamma, setValue: setGamma, min: 0, max: 1, },

                            ].map((item, index) => (
                                <Box key={index} sx={{ width: 160 }}>
                                    <Typography sx={{ fontSize: "14px", mb: 1 }}>
                                        {item.label}{" "}
                                        <span style={{ fontWeight: 700 }}>{item.value.toFixed(2)}</span>
                                    </Typography>

                                    <Slider
                                        value={item.value}
                                        min={item.min}
                                        max={item.max}
                                        step={0.01}
                                        disabled={!editable}
                                        onChange={(e, val) => item.setValue(val)}
                                    />
                                </Box>
                            ))}

                            {/* TREND TYPE */}
                            {/* <Box>
                                <Typography sx={{ mb: 1, fontSize: "13px", fontWeight: 700 }}>
                                    TREND TYPE
                                </Typography>
                                <FormControl sx={inputStyle}>
                                    <Select
                                        value={trendType}
                                        onChange={(e) => setTrendType(e.target.value)}
                                        disabled={!editable}
                                        size="small"
                                        displayEmpty
                                    >
                                        <MenuItem value="" disabled>
                                            Select Trend Type
                                        </MenuItem>
                                        <MenuItem value="additive">Additive</MenuItem>
                                        <MenuItem value="multiplicative">Multiplicative</MenuItem>
                                    </Select>
                                </FormControl>
                            </Box> */}
                        </>
                        {/* )} */}

                        {/* TRAJECTORY BLOCK */}
                        {showTrajectory && (
                            <>
                                {/* <Box sx={{ borderLeft: "10px solid #d1d5db"}} /> */}
                                <Divider orientation="vertical" flexItem sx={{ mx: 0 }} />

                                <Box>
                                    <Typography sx={{ mb: 1, fontSize: "13px", fontWeight: 700 }}>
                                        TRAJECTORY START
                                    </Typography>

                                    <FormControl sx={inputStyle}>
                                        <Select
                                            value={trajectoryStart}
                                            onChange={(e) => setTrajectoryStart(e.target.value)}
                                            disabled={!editable}
                                        >
                                            {chartData?.months?.map((month) => (
                                                <MenuItem key={month} value={month}>
                                                    {new Date(month).toLocaleDateString("en-US", {
                                                        month: "short",
                                                        year: "2-digit",
                                                    })}
                                                </MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Box>

                                <Box>
                                    <Typography sx={{ mb: 1, fontSize: "13px", fontWeight: 700 }}>
                                        GROWTH TYPE
                                    </Typography>

                                    <FormControl sx={inputStyle}>
                                        <Select
                                            value={growthType}
                                            onChange={(e) => setGrowthType(e.target.value)}
                                            disabled={!editable}
                                        >
                                            <MenuItem value="linear">Linear</MenuItem>
                                            <MenuItem value="exponential">Exponential</MenuItem>
                                            <MenuItem value="logarithmic">Logarithmic</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Box>

                                <Box sx={{ width: 220 }}>
                                    <Typography sx={{ mb: 1 }}>
                                        Total Growth % <b>{totalGrowth.toFixed(1)}%</b>
                                    </Typography>

                                    <Slider
                                        value={totalGrowth}
                                        min={0}
                                        max={100}
                                        step={0.1}
                                        disabled={!editable}
                                        onChange={(e, val) => setTotalGrowth(val)}
                                    />
                                </Box>

                                <Box sx={{ width: 200 }}>
                                    <Typography sx={{ mb: 1 }}>
                                        Duration (Mos) <b>{duration}</b>
                                    </Typography>

                                    <Slider
                                        value={duration}
                                        min={0}
                                        max={24}
                                        step={1}
                                        disabled={!editable}
                                        onChange={(e, val) => setDuration(val)}
                                    />
                                </Box>
                            </>
                        )}

                        <Divider orientation="vertical" flexItem sx={{ mx: 0 }} />

                        <Box sx={{ width: 160 }}>
                            <Typography sx={{ mb: 1 }}>
                                MULTIPLIER{" "}
                                <span style={{ fontWeight: 700 }}>
                                    {multiplier.toFixed(2)}
                                </span>
                            </Typography>

                            <Slider
                                value={multiplier}
                                min={0}
                                max={3}
                                step={0.01}
                                disabled={!editable}
                                onChange={(e, val) => setMultiplier(val)}
                            />
                        </Box>

                        {/* RECALCULATE */}
                        <Button
                            variant="contained"
                            disabled={!editable}
                            onClick={handleRecalculate}
                            sx={{ height: "35px", mt: 3, textTransform: "none", backgroundColor: "#6b7280", borderRadius: "8px" }}>
                            Refresh
                        </Button>
                    </Box>
                </Paper>
                <ForecastTrendChart
                    therapyArea={therapyArea}
                    indication={indication}
                    metric={metric}
                    selectedProduct={brand}
                    selectedLot={lot}
                    chartData={chartData}
                    tableData={tableData}
                    updateChartData={setChartData}
                    updateTableData={setTableData}
                />
            </Paper>
        </Box>
    );
}