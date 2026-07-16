import React, { useState, useContext, useEffect } from "react";

import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    TextField,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
} from "@mui/material";

import Tooltip from "@mui/material/Tooltip";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

import { GlobalContext } from "../../../context/Provider";

import dayjs from "dayjs";
import HIVMarketAnalysis from "./HIVMarketAnalysis";
import { getHIVModelInputFilters, applyHIVScenario, recalculateHIVScenario, editHIVScenario, saveHIVScenario, applySelectedHIVScenario, updateHIVScenario } from "../../../services/apiService";
import { useLoadingStore } from "../../../stores";

const globalConfigDateLocaleText = {
    fieldMonthPlaceholder: () => "MM",
    fieldYearPlaceholder: () => "YYYY",
};

export default function HIVModelInput() {
    const { favState } = useContext(GlobalContext);

    const therapyArea = favState?.selectedTherapyArea || "HIV";

    // ---------------- FILTERS ----------------

    const [fromDate, setFromDate] = useState("2024-01-01");
    const [toDate, setToDate] = useState("2025-12-01");

    const { setLoading } = useLoadingStore();

    const [availableMonths, setAvailableMonths] = useState([]);
    const [markets, setMarkets] = useState([]);
    const [products, setProducts] = useState([]);

    // const [metricFilter, setMetricFilter] =
    //     useState("market_volume");

    const [marketFilter, setMarketFilter] =
        useState("retail");

    const [productFilter, setProductFilter] =
        useState("Truvada");

    // ---------------- PROJECTION ENGINE ----------------

    const [editable, setEditable] =
        useState(false);

    const [modelSelection, setModelSelection] =
        useState("ets");

    const [alpha, setAlpha] =
        useState(0);

    const [beta, setBeta] =
        useState(0);

    const [gamma, setGamma] =
        useState(0);

    const [totalGrowth, setTotalGrowth] =
        useState(0);

    const [duration, setDuration] =
        useState(0);

    const [numberOfMonths, setNumberOfMonths] = useState(3);

    const [kValue, setKValue] =
        useState(0);

    const [trajectoryStart, setTrajectoryStart] =
        useState("");

    const [multiplier, setMultiplier] =
        useState(0);

    const [multiplierHorizon, setMultiplierHorizon] =
        useState("Forecast");

    // const [openSaveScenario, setOpenSaveScenario] =
    //     useState(false);

    // const [scenarioName, setScenarioName] =
    //     useState("");

    const [projectionFactors, setProjectionFactors] =
        useState(null);

    const [marketAnalysis, setMarketAnalysis] =
        useState(null);

    const [availableScenarios, setAvailableScenarios] = useState([]);

    const [activeScenario, setActiveScenario] =
        useState("");

    const [trajectoryMonthOptions, setTrajectoryMonthOptions] =
        useState([]);

    const [activeTab, setActiveTab] = useState("total_market_volume");

    const [selectedMetric, setSelectedMetric] = useState("market_volume");

    const [allScenariosData, setAllScenariosData] = useState({});

    // const [showAnalysis, setShowAnalysis] =
    //     useState(false);

    useEffect(() => {
        if (therapyArea) {
            fetchModelInputFilters();
        }
    }, [therapyArea]);

    useEffect(() => {
        if (!projectionFactors) return;

        // ETS

        const ets = projectionFactors.ets || {};

        setAlpha(ets.alpha ?? 0);
        setBeta(ets.beta ?? 0);
        setGamma(ets.gamma ?? 0);

        // Selected model

        const model =
            projectionFactors[modelSelection] || {};

        setTotalGrowth(
            model.total_growth ?? 0
        );

        setDuration(
            model.duration ?? 12
        );

        setNumberOfMonths(
            model.window ?? 3
        );

        setTrajectoryStart(
            model.trajectory_start || ""
        );

        setKValue(
            model.k_value ?? 1
        );

        // Common

        setMultiplier(
            projectionFactors.multiplier ?? 1
        );

        setMultiplierHorizon(
            projectionFactors.multiplier_horizon ??
            "Forecast"
        );

    }, [modelSelection, projectionFactors]);

    const fetchModelInputFilters = async () => {
        try {
            setLoading(true);

            const response = await getHIVModelInputFilters(therapyArea);
            const resData = response?.data;

            setAvailableMonths(resData?.available_months || []);
            setMarkets(resData?.markets || []);
            setProducts(resData?.products || []);

            const defaultFilter = resData?.selected_filter;

            if (defaultFilter) {
                setFromDate(defaultFilter.start_date || "");
                setToDate(defaultFilter.end_date || "");
                setMarketFilter(defaultFilter.market || "");
                setProductFilter(defaultFilter.product || "");

                // Auto load saved scenario
                const payload = {
                    ta_name: therapyArea,
                    selected_filter: {
                        start_date: defaultFilter.start_date,
                        end_date: defaultFilter.end_date,
                        market: defaultFilter.market,
                        product: defaultFilter.product,
                    },
                };

                const applyResponse = await applyHIVScenario(payload);

                const scenario =
                    applyResponse.data.scenarios[
                    applyResponse.data.active_scenario
                    ];

                const factors = scenario?.factors || {};

                setProjectionFactors(factors);

                setModelSelection(
                    factors.active_model || "ets"
                );

                setAvailableScenarios(
                    applyResponse.data.available_scenarios || []
                );

                setActiveScenario(
                    applyResponse.data.active_scenario || ""
                );

                setMarketAnalysis(
                    scenario?.market_analysis || {}
                );

                setAllScenariosData(applyResponse.data.scenarios || {});

                const chartData =
                    scenario?.market_analysis
                        ?.total_market_volume
                        ?.market_volume
                        ?.monthly
                        ?.chart;

                setTrajectoryMonthOptions(
                    (chartData?.months?.slice(chartData?.forecast_start_index) || []).map(
                        (month) => ({
                            value: dayjs(month, "MMM-YY").format("YYYY-MM-DD"),
                            label: month,
                        })
                    )
                );
            } else {
                setFromDate("");
                setToDate("");
                setMarketFilter("");
                setProductFilter("");
            }
        } catch (error) {
            console.error("Failed to fetch model input filters", error);

            setAvailableMonths([]);
            setMarkets([]);
            setProducts([]);

            setFromDate("");
            setToDate("");
            setMarketFilter("");
            setProductFilter("");
        } finally {
            setLoading(false);
        }
    };

    const handleApplyFilter = async () => {
        try {
            setLoading(true);

            const payload = {
                ta_name: therapyArea,
                selected_filter: {
                    start_date: fromDate,
                    end_date: toDate,
                    market: marketFilter,
                    product: productFilter,
                },
            };

            const response =
                await applyHIVScenario(payload);

            const scenario =
                response.data.scenarios[
                response.data.active_scenario
                ];

            const factors =
                scenario?.factors || {};

            setProjectionFactors(factors);

            setModelSelection(
                factors.active_model || "ets"
            );

            setAvailableScenarios(
                response.data.available_scenarios || []
            );

            setActiveScenario(
                response.data.active_scenario || ""
            );

            setMarketAnalysis(
                scenario?.market_analysis || {}
            );

            setAllScenariosData(response.data.scenarios || {});

            console.log(
                scenario.market_analysis
            );

            const chartData =
                scenario?.market_analysis
                    ?.total_market_volume
                    ?.market_volume
                    ?.monthly
                    ?.chart;

            setTrajectoryMonthOptions(
                (chartData?.months?.slice(chartData?.forecast_start_index) || []).map(
                    (month) => ({
                        value: dayjs(month, "MMM-YY").format("YYYY-MM-DD"),
                        label: month,
                    })
                )
            );

            // setShowAnalysis(true);

            // Projection Engine

            // setModelSelection(
            //     factors.active_model || "ets"
            // );

            // setMultiplier(
            //     factors.multiplier ?? 1
            // );

            // setMultiplierHorizon(
            //     factors.multiplier_horizon ??
            //     "Forecast"
            // );

            // const ets =
            //     factors.ets || {};

            // setAlpha(ets.alpha ?? 0);
            // setBeta(ets.beta ?? 0);
            // setGamma(ets.gamma ?? 0);

            // const growth =
            //     factors[
            //     factors.active_model
            //     ] || {};

            // setTotalGrowth(
            //     growth.total_growth ?? 0
            // );

            // setDuration(
            //     growth.duration ?? 12
            // );

            // setTrajectoryStart(
            //     growth.trajectory_start || ""
            // );

            // setKValue(
            //     growth.k_value ?? 1
            // );
        } catch (err) {
            console.log(err);
        } finally {
            setLoading(false);
        }
    };

    const handleRecalculate = async () => {
        try {
            setLoading(true);

            const payload = {
                ta_name: therapyArea,

                selected_filter: {
                    start_date: fromDate,
                    end_date: toDate,
                    market: marketFilter,
                    product: productFilter,
                },

                scenario_name: activeScenario,

                selected_tab: activeTab,

                metric: selectedMetric,

                model_type: modelSelection,

                factors: {
                    multiplier: Number(multiplier),

                    multiplier_horizon: multiplierHorizon,

                    ...(modelSelection === "ets"
                        ? {
                            ets: {
                                alpha: Number(alpha),
                                beta: Number(beta),
                                gamma: Number(gamma),
                            },
                        }
                        : modelSelection === "moving_average"
                            ? {
                                growth: {
                                    window: Number(numberOfMonths),
                                },
                            }
                            : {
                                growth: {
                                    total_growth: Number(totalGrowth),
                                    duration: Number(duration),
                                    k_value:
                                        modelSelection === "linear"
                                            ? 0
                                            : Number(kValue),
                                    trajectory_start: trajectoryStart,
                                },
                            }),
                },
            };

            console.log("paylod--->", payload)

            const response =
                await recalculateHIVScenario(
                    payload
                );

            const scenario =
                response.data.scenarios[
                response.data.active_scenario
                ];

            const factors =
                scenario?.factors || {};

            setProjectionFactors(factors);

            setModelSelection(
                factors.active_model ||
                modelSelection
            );

            setAvailableScenarios(
                response.data.available_scenarios ||
                []
            );

            setActiveScenario(
                response.data.active_scenario ||
                ""
            );

            setMarketAnalysis(
                scenario.market_analysis || {}
            );

            setAllScenariosData(response.data.scenarios || {});

        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleEdit = async (updatedMarketAnalysis, editedRows) => {
        try {
            setLoading(true);

            const payload = {
                ta_name: therapyArea,

                selected_filter: {
                    start_date: fromDate,
                    end_date: toDate,
                    market: marketFilter,
                    product: productFilter,
                },

                scenario_name: activeScenario,

                model_type: modelSelection,

                factors: {
                    multiplier: Number(multiplier),

                    multiplier_horizon: multiplierHorizon,

                    ...(modelSelection === "ets"
                        ? {
                            ets: {
                                alpha: Number(alpha),
                                beta: Number(beta),
                                gamma: Number(gamma),
                            },
                        }
                        : modelSelection === "moving_average"
                            ? {
                                growth: {
                                    window: Number(numberOfMonths),
                                },
                            }
                            : {
                                growth: {
                                    total_growth: Number(totalGrowth),
                                    duration: Number(duration),
                                    k_value:
                                        modelSelection === "linear"
                                            ? 0
                                            : Number(kValue),
                                    trajectory_start: trajectoryStart,
                                },
                            }),
                },

                selected_tab: activeTab,

                selected_metric: selectedMetric,

                edited_rows: editedRows,

                market_analysis: updatedMarketAnalysis,
            };

            console.log("Edit Payload", payload);

            const response = await editHIVScenario(payload);

            const scenario =
                response.data.scenarios[
                response.data.active_scenario
                ];

            setProjectionFactors(
                scenario.factors || {}
            );

            setAvailableScenarios(
                response.data.available_scenarios || []
            );

            setActiveScenario(
                response.data.active_scenario || ""
            );

            setMarketAnalysis(
                scenario.market_analysis || {}
            );

            setAllScenariosData(response.data.scenarios || {});

        } catch (err) {
            console.error(err);
            throw err; // let handleRefresh know it failed

        } finally {
            setLoading(false);
        }
    };

    const handleSaveScenario = async (scenarioName) => {
        try {
            setLoading(true);

            const payload = {
                ta_name: therapyArea,

                selected_filter: {
                    start_date: fromDate,
                    end_date: toDate,
                    market: marketFilter,
                    product: productFilter,
                },

                scenario_name: scenarioName,

                model_type: modelSelection,

                factors: {
                    multiplier: Number(multiplier),

                    multiplier_horizon: multiplierHorizon,

                    ...(modelSelection === "ets"
                        ? {
                            ets: {
                                alpha: Number(alpha),
                                beta: Number(beta),
                                gamma: Number(gamma),
                            },
                        }
                        : modelSelection === "moving_average"
                            ? {
                                growth: {
                                    window: Number(numberOfMonths),
                                },
                            }
                            : {
                                growth: {
                                    total_growth: Number(totalGrowth),
                                    duration: Number(duration),
                                    k_value:
                                        modelSelection === "linear"
                                            ? 0
                                            : Number(kValue),
                                    trajectory_start: trajectoryStart,
                                },
                            }),
                },

                market_analysis: JSON.parse(
                    JSON.stringify(marketAnalysis)
                ),
            };

            console.log("Save Scenario Payload", payload);

            const response =
                await saveHIVScenario(payload);

            const scenario =
                response.data.scenarios[
                response.data.active_scenario
                ];

            setProjectionFactors(
                scenario.factors || {}
            );

            setAvailableScenarios(
                response.data.available_scenarios || []
            );

            setActiveScenario(
                response.data.active_scenario || ""
            );

            setMarketAnalysis(
                scenario.market_analysis || {}
            );

            setAllScenariosData(response.data.scenarios || {});

        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleUpdateScenario = async () => {
        try {
            setLoading(true);

            const payload = {
                ta_name: therapyArea,

                selected_filter: {
                    start_date: fromDate,
                    end_date: toDate,
                    market: marketFilter,
                    product: productFilter,
                },

                scenario_name: activeScenario,

                model_type: modelSelection,

                factors: {
                    multiplier: Number(multiplier),

                    multiplier_horizon: multiplierHorizon,

                    ...(modelSelection === "ets"
                        ? {
                            ets: {
                                alpha: Number(alpha),
                                beta: Number(beta),
                                gamma: Number(gamma),
                            },
                        }
                        : modelSelection === "moving_average"
                            ? {
                                growth: {
                                    window: Number(numberOfMonths),
                                },
                            }
                            : {
                                growth: {
                                    total_growth: Number(totalGrowth),
                                    duration: Number(duration),
                                    k_value:
                                        modelSelection === "linear"
                                            ? 0
                                            : Number(kValue),
                                    trajectory_start: trajectoryStart,
                                },
                            }),
                },

                market_analysis: JSON.parse(
                    JSON.stringify(marketAnalysis)
                ),
            };

            const response = await updateHIVScenario(
                activeScenario,
                payload
            );

            const scenario =
                response.data.scenarios[
                response.data.active_scenario
                ];

            setProjectionFactors(scenario.factors || {});
            setAvailableScenarios(response.data.available_scenarios || []);
            setActiveScenario(response.data.active_scenario || "");
            setMarketAnalysis(scenario.market_analysis || {});
            setAllScenariosData(response.data.scenarios || {});
        } finally {
            setLoading(false);
        }
    };

    const handleApplySelectedScenario = async (scenarioName) => {
        try {
            setLoading(true);

            const payload = {
                ta_name: therapyArea,

                selected_filter: {
                    start_date: fromDate,
                    end_date: toDate,
                    market: marketFilter,
                    product: productFilter,
                },

                scenario_name: scenarioName,
            };

            console.log(
                "Apply Selected Scenario Payload",
                payload
            );

            const response =
                await applySelectedHIVScenario(payload);

            const scenario =
                response.data.scenarios[
                response.data.active_scenario
                ];

            const factors =
                scenario?.factors || {};

            setProjectionFactors(factors);

            setModelSelection(
                factors.active_model || "ets"
            );

            setAvailableScenarios(
                response.data.available_scenarios || []
            );

            setActiveScenario(
                response.data.active_scenario || ""
            );

            setMarketAnalysis(
                scenario.market_analysis || {}
            );

            setAllScenariosData(response.data.scenarios || {});

        } catch (err) {

            console.error(err);

        } finally {

            setLoading(false);

        }
    };


    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "170px",

        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
        },
    };

    const recalculateInputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "110px",

        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
        },
    };

    // const handleTabChange = (tab) => {
    //     setActiveTab(tab);

    //     if (tab === "total_market_volume") {
    //         setModelSelection("ets");
    //     } else {
    //         setModelSelection("linear");
    //     }
    // };

    const DEFAULT_METRIC_BY_TAB = {
        total_market_volume: "market_volume",
        market_distribution: "market_share",
        product_distribution: "market_share",
        market_product: "market_volume",
        product_market: "market_volume",
    };

    const handleTabChange = (tab) => {
        setActiveTab(tab);

        const metric = DEFAULT_METRIC_BY_TAB[tab];
        setSelectedMetric(metric);

        if (tab === "total_market_volume") {
            setModelSelection("ets");
        } else {
            setModelSelection("moving_average");
        }
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
                {/* ===================== TOP FILTERS ===================== */}

                <Box
                    sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "end",
                        gap: 3,
                        flexWrap: "wrap",
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
                        {/* THERAPY AREA */}

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
                                    minWidth: "150px",
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

                        {/* FROM DATE */}

                        <Box>
                            <Typography
                                sx={{
                                    mb: 1,
                                    fontSize: "14px",
                                    fontWeight: 700,
                                    color: "#64748b",
                                }}
                            >
                                FROM DATE
                            </Typography>

                            <LocalizationProvider
                                dateAdapter={AdapterDayjs}
                                localeText={globalConfigDateLocaleText}
                            >
                                <FormControl sx={inputStyle}>
                                    <Select
                                        value={fromDate}
                                        onChange={(e) => setFromDate(e.target.value)}
                                        renderValue={(selected) =>
                                            dayjs(selected).format("MMM YY")
                                        }
                                        MenuProps={{
                                            PaperProps: {
                                                sx: {
                                                    maxHeight: 300,
                                                    width: 130,
                                                    "& .MuiMenuItem-root": {
                                                        minHeight: 32,
                                                        fontSize: "15px",
                                                        py: 0.5,
                                                    },
                                                },
                                            },
                                        }}
                                    >
                                        {availableMonths.map((month) => (
                                            <MenuItem
                                                key={month}
                                                value={month}
                                            >
                                                {dayjs(month).format("MMM YY")}
                                            </MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>
                            </LocalizationProvider>
                        </Box>

                        {/* TO DATE */}

                        <Box>
                            <Typography
                                sx={{
                                    mb: 1,
                                    fontSize: "14px",
                                    fontWeight: 700,
                                    color: "#64748b",
                                }}
                            >
                                TO DATE
                            </Typography>

                            <LocalizationProvider
                                dateAdapter={AdapterDayjs}
                                localeText={globalConfigDateLocaleText}
                            >
                                <FormControl sx={inputStyle}>
                                    <Select
                                        value={toDate}
                                        onChange={(e) => setToDate(e.target.value)}
                                        renderValue={(selected) =>
                                            dayjs(selected).format("MMM YY")
                                        }
                                        MenuProps={{
                                            PaperProps: {
                                                sx: {
                                                    maxHeight: 300,
                                                    width: 130,
                                                    "& .MuiMenuItem-root": {
                                                        minHeight: 32,
                                                        fontSize: "15px",
                                                        py: 0.5,
                                                    },
                                                },
                                            },
                                        }}
                                    >
                                        {availableMonths
                                            .filter((m) =>
                                                dayjs(m).isAfter(fromDate)
                                            )
                                            .map((month) => (
                                                <MenuItem
                                                    key={month}
                                                    value={month}
                                                >
                                                    {dayjs(month).format("MMM YY")}
                                                </MenuItem>
                                            ))}
                                    </Select>
                                </FormControl>
                            </LocalizationProvider>
                        </Box>

                        {/* METRIC FILTER */}

                        {/* <Box>
                            <Typography
                                sx={{
                                    mb: 1,
                                    fontSize: "14px",
                                    fontWeight: 700,
                                    color: "#64748b",
                                }}
                            >
                                METRIC FILTER
                            </Typography>

                            <FormControl sx={inputStyle}>
                                <Select
                                    value={metricFilter}
                                    onChange={(e) =>
                                        setMetricFilter(e.target.value)
                                    }
                                >
                                    <MenuItem value="market_volume">
                                        Market Volume
                                    </MenuItem>

                                    <MenuItem value="market_share">
                                        Market Share
                                    </MenuItem>
                                </Select>
                            </FormControl>
                        </Box> */}

                        {/* MARKET FILTER */}

                        <Box>
                            <Typography
                                sx={{
                                    mb: 1,
                                    fontSize: "14px",
                                    fontWeight: 700,
                                    color: "#64748b",
                                }}
                            >
                                MARKET FILTER
                            </Typography>

                            <FormControl sx={inputStyle}>
                                <Select
                                    value={marketFilter}
                                    onChange={(e) =>
                                        setMarketFilter(e.target.value)
                                    }
                                >
                                    {markets.map((market) => (
                                        <MenuItem
                                            key={market}
                                            value={market}
                                        >
                                            {market}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Box>

                        {/* PRODUCT */}

                        <Box>
                            <Typography
                                sx={{
                                    mb: 1,
                                    fontSize: "14px",
                                    fontWeight: 700,
                                    color: "#64748b",
                                }}
                            >
                                PRODUCT FILTER
                            </Typography>

                            <FormControl sx={inputStyle}>
                                <Select
                                    value={productFilter}
                                    onChange={(e) =>
                                        setProductFilter(e.target.value)
                                    }
                                >
                                    {products.map((product) => (
                                        <MenuItem
                                            key={product}
                                            value={product}
                                        >
                                            {product}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Box>

                        <Box
                            sx={{
                                display: "flex",
                                gap: 1.5,
                                alignItems: "center",
                            }}
                        >
                            <Button
                                variant="contained"
                                onClick={handleApplyFilter}
                                sx={{
                                    textTransform: "none",
                                    borderRadius: "8px",
                                    backgroundColor: "#4F46E5",
                                }}
                            >
                                Apply Filter
                            </Button>

                            {/* <Button
                                variant="outlined"
                                onClick={() => setOpenSaveScenario(true)}
                                sx={{
                                    textTransform: "none",
                                    borderRadius: "8px",
                                }}
                            >
                                Save Scenario
                            </Button> */}
                        </Box>
                    </Box>
                </Box>

                {/* ===================== STATISTICAL ENGINE ===================== */}
                {/* {showAnalysis && ( */}

                <Paper
                    sx={{ mt: 3, p: 3, borderRadius: "16px", border: "1px solid #D8DEE8", boxShadow: "none", backgroundColor: editable ? "#fff" : "#eff6ff", }} >
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                        <Typography sx={{ fontSize: "14px", fontWeight: 700, color: "#1d4ed8", textTransform: "uppercase" }} > STATISTICAL PROJECTION ENGINE </Typography>
                        <Box display="flex" gap={2}>
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

                    <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap", alignItems: "center" }}>
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
                                    <MenuItem value="moving_average">Moving Average </MenuItem>
                                    <MenuItem value="linear">Linear</MenuItem>
                                    <MenuItem value="exponential">Exponential</MenuItem>
                                    <MenuItem value="logarithmic">Logarithmic</MenuItem>
                                    <MenuItem value="scurve">S-Curve</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>

                        {/* ETS BLOCK */}
                        {modelSelection === "ets" && (
                            <>
                                <Box>
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                        <Typography sx={{ fontSize: "14px" }}>
                                            LEVEL (α)
                                        </Typography>

                                        <Tooltip title="Please enter value from 0 to 1" arrow placement="top">
                                            <InfoOutlinedIcon
                                                sx={{
                                                    fontSize: 16,
                                                    color: "#64748b",
                                                    cursor: "pointer",
                                                }}
                                            />
                                        </Tooltip>
                                    </Box>
                                    <TextField
                                        type="number"
                                        value={alpha}
                                        disabled={!editable}
                                        onChange={(e) => {
                                            const value = e.target.value;

                                            if (
                                                value === "" ||
                                                (Number(value) >= 0 && Number(value) <= 1)
                                            ) {
                                                setAlpha(value);
                                            }
                                        }}
                                        inputProps={{
                                            min: 0,
                                            max: 1,
                                            step: 0.01,
                                        }}
                                        sx={recalculateInputStyle}
                                    />
                                </Box>

                                <Box>
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                        <Typography sx={{ fontSize: "14px" }}>
                                            TREND (β)
                                        </Typography>

                                        <Tooltip title="Please enter value from 0 to 1" arrow placement="top">
                                            <InfoOutlinedIcon
                                                sx={{
                                                    fontSize: 16,
                                                    color: "#64748b",
                                                    cursor: "pointer",
                                                }}
                                            />
                                        </Tooltip>
                                    </Box>
                                    <TextField
                                        type="number"
                                        value={beta}
                                        disabled={!editable}
                                        onChange={(e) => {
                                            const value = e.target.value;

                                            if (
                                                value === "" ||
                                                (Number(value) >= 0 && Number(value) <= 1)
                                            ) {
                                                setBeta(value);
                                            }
                                        }}
                                        inputProps={{
                                            min: 0,
                                            max: 1,
                                            step: 0.01,
                                        }}
                                        sx={recalculateInputStyle}
                                    />
                                </Box>

                                <Box>
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                        <Typography sx={{ fontSize: "14px" }}>
                                            DAMPING (φ)
                                        </Typography>
                                        <Tooltip title="Please enter value from 0 to 1" arrow placement="top">
                                            <InfoOutlinedIcon
                                                sx={{
                                                    fontSize: 16,
                                                    color: "#64748b",
                                                    cursor: "pointer",
                                                }}
                                            />
                                        </Tooltip>
                                    </Box>
                                    <TextField
                                        type="number"
                                        value={gamma}
                                        disabled={!editable}
                                        onChange={(e) => {
                                            const value = e.target.value;

                                            if (
                                                value === "" ||
                                                (Number(value) >= 0 && Number(value) <= 1)
                                            ) {
                                                setGamma(value);
                                            }
                                        }}
                                        inputProps={{
                                            min: 0,
                                            max: 1,
                                            step: 0.01,
                                        }}
                                        sx={recalculateInputStyle}
                                    />
                                </Box>
                            </>
                        )}

                        {modelSelection === "moving_average" && (
                            <Box>
                                <Box
                                    sx={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: 0.5,
                                        mb: 1,
                                    }}
                                >
                                    <Typography sx={{ fontSize: "14px" }}>
                                        NUMBER OF MONTHS
                                    </Typography>

                                    <Tooltip
                                        title="Please enter the number of months"
                                        arrow
                                        placement="top"
                                    >
                                        <InfoOutlinedIcon
                                            sx={{
                                                fontSize: 16,
                                                color: "#64748b",
                                                cursor: "pointer",
                                            }}
                                        />
                                    </Tooltip>
                                </Box>

                                <TextField
                                    type="number"
                                    value={numberOfMonths}
                                    disabled={!editable}
                                    onChange={(e) =>
                                        setNumberOfMonths(Number(e.target.value))
                                    }
                                    inputProps={{
                                        min: 1,
                                        max: 24,
                                        step: 1,
                                    }}
                                    sx={recalculateInputStyle}
                                />
                            </Box>
                        )}

                        {["linear", "exponential", "logarithmic", "scurve"].includes(modelSelection) && (
                            <>
                                <Box>
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                        <Typography sx={{ fontSize: "14px" }}>
                                            GROWTH %
                                        </Typography>
                                        <Tooltip title="Please enter the total growth%" arrow placement="top">
                                            <InfoOutlinedIcon
                                                sx={{
                                                    fontSize: 16,
                                                    color: "#64748b",
                                                    cursor: "pointer",
                                                }}
                                            />
                                        </Tooltip>
                                    </Box>
                                    <TextField
                                        type="number"
                                        value={totalGrowth}
                                        disabled={!editable}
                                        onChange={(e) => {
                                            const value = e.target.value;

                                            if (
                                                value === "" ||
                                                (Number(value) >= -100 && Number(value) <= 100)
                                            ) {
                                                setTotalGrowth(value);
                                            }
                                        }}
                                        inputProps={{
                                            min: 0,
                                            max: 100,
                                            step: 0.1,
                                        }}
                                        sx={recalculateInputStyle}
                                    />
                                </Box>

                                <Box>
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                        <Typography sx={{ fontSize: "14px" }}>
                                            DURATION
                                        </Typography>
                                        <Tooltip title="Please enter the months" arrow placement="top">
                                            <InfoOutlinedIcon
                                                sx={{
                                                    fontSize: 16,
                                                    color: "#64748b",
                                                    cursor: "pointer",
                                                }}
                                            />
                                        </Tooltip>
                                    </Box>

                                    <TextField
                                        type="number"
                                        value={duration}
                                        disabled={!editable}
                                        onChange={(e) => setDuration(Number(e.target.value))}
                                        inputProps={{
                                            min: 0,
                                            max: 100,
                                            step: 1,
                                        }}
                                        sx={recalculateInputStyle}
                                    />
                                </Box>

                                {modelSelection !== "linear" && (
                                    <Box>
                                        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                            <Typography sx={{ fontSize: "14px" }}>
                                                K VALUE
                                            </Typography>
                                            <Tooltip title="Please enter value from 0 to 3" arrow placement="top">
                                                <InfoOutlinedIcon
                                                    sx={{
                                                        fontSize: 16,
                                                        color: "#64748b",
                                                        cursor: "pointer",
                                                    }}
                                                />
                                            </Tooltip>
                                        </Box>

                                        <TextField
                                            type="number"
                                            value={kValue}
                                            disabled={!editable}
                                            onChange={(e) => {
                                                const value = e.target.value;

                                                if (
                                                    value === "" ||
                                                    (Number(value) >= 0 && Number(value) <= 3)
                                                ) {
                                                    setKValue(value);
                                                }
                                            }}
                                            inputProps={{
                                                min: 0,
                                                max: 3,
                                                step: 0.01,
                                            }}
                                            sx={recalculateInputStyle}
                                        />
                                    </Box>
                                )}

                                <Box>
                                    <Typography sx={{ mb: 1, fontSize: "14px" }}>
                                        TRAJECTORY START
                                    </Typography>

                                    <FormControl sx={recalculateInputStyle}>
                                        <Select
                                            value={trajectoryStart}
                                            onChange={(e) => setTrajectoryStart(e.target.value)}
                                            MenuProps={{
                                                PaperProps: {
                                                    sx: {
                                                        maxHeight: 300,
                                                        width: 130,
                                                        "& .MuiMenuItem-root": {
                                                            minHeight: 32,
                                                            fontSize: "15px",
                                                            py: 0.5,
                                                        },
                                                    },
                                                },
                                            }}
                                            disabled={!editable}
                                        >
                                            {trajectoryMonthOptions.map((month) => (
                                                <MenuItem
                                                    key={month.value}
                                                    value={month.value}
                                                >
                                                    {month.label}
                                                </MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Box>
                            </>
                        )}

                        <Box>
                            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                <Typography sx={{ fontSize: "14px" }}>
                                    MULTIPLIER
                                </Typography>
                                <Tooltip title="Please enter value from 1 to 5" arrow placement="top">
                                    <InfoOutlinedIcon
                                        sx={{
                                            fontSize: 16,
                                            color: "#64748b",
                                            cursor: "pointer",
                                        }}
                                    />
                                </Tooltip>
                            </Box>

                            <TextField
                                type="number"
                                value={multiplier}
                                disabled={!editable}
                                onChange={(e) => {
                                    const value = e.target.value;

                                    if (
                                        value === "" ||
                                        (Number(value) >= 0 && Number(value) <= 5)
                                    ) {
                                        setMultiplier(value);
                                    }
                                }}
                                inputProps={{
                                    min: 0,
                                    max: 2,
                                    step: 0.01,
                                }}
                                sx={recalculateInputStyle}
                            />
                        </Box>
                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px" }}>
                                MULTIPLIER HORIZON
                            </Typography>

                            <FormControl sx={inputStyle}>
                                <Select
                                    value={multiplierHorizon}
                                    onChange={(e) => setMultiplierHorizon(e.target.value)}
                                    disabled={!editable}
                                >
                                    <MenuItem value="History">History</MenuItem>
                                    <MenuItem value="Forecast">Forecast</MenuItem>
                                    <MenuItem value="Both History & Forecast">Both History & Forecast </MenuItem>
                                </Select>
                            </FormControl>
                        </Box>

                        {/* RECALCULATE */}
                        <Button
                            variant="contained"
                            disabled={!editable}
                            onClick={handleRecalculate}
                            sx={{ height: "35px", mt: 3, textTransform: "none", backgroundColor: "#4F46E5", borderRadius: "8px" }}>
                            Recalculate
                        </Button>
                    </Box>
                </Paper>

                {/* )} */}

            </Paper>
            <HIVMarketAnalysis
                marketAnalysis={marketAnalysis}
                allScenariosData={allScenariosData}
                availableScenarios={availableScenarios}
                activeScenario={activeScenario}
                selectedMarket={marketFilter}
                selectedProduct={productFilter}
                onTabChange={handleTabChange}
                selectedMetric={selectedMetric}
                setSelectedMetric={setSelectedMetric}
                onEdit={handleEdit}
                onSaveScenario={handleSaveScenario}
                onApplyScenario={handleApplySelectedScenario}
                onUpdateScenario={handleUpdateScenario}
            />
            {/* <Dialog
                open={openSaveScenario}
                onClose={() => setOpenSaveScenario(false)}
                maxWidth="xs"
                fullWidth
                PaperProps={{ sx: { borderRadius: "12px" } }}
            >
                <DialogTitle sx={{ fontWeight: 700, fontSize: "16px", color: "#0f172a", pb: 1 }}>
                    Save Scenario
                </DialogTitle>

                <DialogContent>
                    <Typography sx={{ fontSize: "13px", color: "#64748b", mb: 2 }}>
                        Enter a name for this scenario.
                    </Typography>
                    <TextField
                        autoFocus
                        fullWidth
                        label="Scenario Name"
                        placeholder="Enter scenario name"
                        value={scenarioName}
                        onChange={(e) =>
                            setScenarioName(e.target.value)
                        }
                        variant="outlined"
                        sx={{ "& .MuiOutlinedInput-root": { borderRadius: "8px" } }}
                    />
                </DialogContent>

                <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}>
                    <Button
                        variant="outlined"
                        onClick={() => {
                            setOpenSaveScenario(false);
                            setScenarioName("");
                        }}
                        sx={{ textTransform: "none", borderRadius: "8px", color: "#64748b", borderColor: "#e2e8f0" }}
                    >
                        Cancel
                    </Button>

                    <Button
                        variant="contained"
                        disabled={!scenarioName.trim()}
                        onClick={() => {
                            console.log({
                                scenarioName,
                                therapyArea,
                                fromDate,
                                toDate,
                                marketFilter,
                                productFilter,
                            });

                            // TODO:
                            // call save scenario API

                            setOpenSaveScenario(false);
                            setScenarioName("");
                        }}
                        sx={{ textTransform: "none", borderRadius: "8px", backgroundColor: "#4F46E5" }}
                    >
                        Save
                    </Button>
                </DialogActions>
            </Dialog> */}
        </Box >
    );
}