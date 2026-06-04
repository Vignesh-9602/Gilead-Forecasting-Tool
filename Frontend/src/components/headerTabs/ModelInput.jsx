import React, { useState, useEffect, useContext } from "react";
import { Box, Paper, Typography, FormControl, Select, MenuItem, TextField, Button, Divider, } from "@mui/material";
import { GlobalContext } from "../../context/Provider";
import ForecastTrendChart from "./ForecastTrendChart";
import { getMetricFilters, applyMetricFilters, recalculateMetrics, saveScenario, updateScenario } from "../../services/apiService";
import { useSnackbarStore, useLoadingStore } from "../../stores";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import Tooltip from "@mui/material/Tooltip";

export default function ModelInput() {
    const { showSnackbar } = useSnackbarStore();
    const { setLoading, isLoading } = useLoadingStore();
    const [scenarioSelector, setScenarioSelector] = useState("");
    const [indication, setIndication] = useState("");
    const [lot, setLot] = useState("");
    const [appliedLot, setAppliedLot] = useState(""); // last applied
    const [metric, setMetric] = useState("");
    const [brand, setBrand] = useState("");
    const [appliedBrand, setAppliedBrand] = useState("");
    // const [scenarioName, setScenarioName] = useState("");
    const [editable, setEditable] = useState(false);

    const [modelSelection, setModelSelection] = useState("ets");
    const [allFactors, setAllFactors] = useState({});

    const [totalGrowth, setTotalGrowth] = useState(10);
    const [duration, setDuration] = useState(12);
    const [kValue, setKValue] = useState(1);

    const [multiplier, setMultiplier] = useState(1.0);
    const [multiplierHorizon, setMultiplierHorizon] = useState("Forecast");

    const [alpha, setAlpha] = useState(0);
    const [beta, setBeta] = useState(0);
    const [gamma, setGamma] = useState(0);

    const [mappingData, setMappingData] = useState({});
    const [filterOptions, setFilterOptions] = useState({
        indications: [],
        metric_filters: [],
        scenario_names: [],
    });

    const [chartData, setChartData] = useState(null);
    const [tableData, setTableData] = useState([]);

    const [allMetricsData, setAllMetricsData] = useState({
        nps: { chart: null, table: [] },
        market_share: { chart: null, table: [] }
    });

    const [etsFactors, setEtsFactors] = useState({});
    const [trajectoryFactors, setTrajectoryFactors] = useState({});

    // const [showTrajectory, setShowTrajectory] = useState(false);
    const [trajectoryStart, setTrajectoryStart] = useState("");

    const { favState } = useContext(GlobalContext);
    const therapyArea = favState?.selectedTherapyArea;

    useEffect(() => {
        if (therapyArea) {
            fetchMetricFilters();
        }
    }, [therapyArea]);

    useEffect(() => {
        if (!allFactors || !Object.keys(allFactors).length) return;

        const selected = modelSelection;

        if (selected === "ets") {
            const ets = allFactors?.ets || {};
            setAlpha(ets?.alpha ?? 0);
            setBeta(ets?.beta ?? 0);
            setGamma(ets?.gamma ?? 0);
        } else {
            const traj = allFactors?.[selected] || {};
            setTotalGrowth(traj?.total_growth ?? 0);
            setDuration(traj?.duration ?? 12);
            setTrajectoryStart(traj?.trajectory_start || "");
            setKValue(traj?.k_value ?? 1);
        }

    }, [modelSelection, allFactors]);

    const fetchMetricFilters = async () => {
        try {
            setLoading(true);
            const response = await getMetricFilters(therapyArea);
            const resData = response?.data;

            setMappingData(resData?.data || {});

            const defaultFilter = resData?.default_filter;

            if (defaultFilter) {
                setScenarioSelector(defaultFilter.scenario_name);
                setIndication(defaultFilter.indication);
                setLot(defaultFilter.lot);
                setMetric(defaultFilter.metric);
                setBrand(defaultFilter.product || "");

                setFilterOptions({
                    indications: Object.keys(
                        resData?.data?.[
                        defaultFilter.scenario_name
                        ] || {}
                    ),
                    metric_filters: resData?.metric_filters || [],
                    scenario_names: resData?.scenario_names || [],
                });

                // Auto apply filter with default values
                const payload = {
                    ta_name: therapyArea,
                    scenario_name: defaultFilter.scenario_name,
                    indications: [defaultFilter.indication],
                    lots: [defaultFilter.lot],
                    metric_filter: defaultFilter.metric,
                    product:
                        defaultFilter.metric === "market_share"
                            ? defaultFilter.product || ""
                            : "",
                };

                const applyResponse = await applyMetricFilters(payload);
                const data = applyResponse?.data;

                setAppliedLot(defaultFilter.lot);
                setAppliedBrand(defaultFilter.product || "");

                const factors = data?.factors || {};
                const activeModel = factors?.active_model || "ets";

                setModelSelection(activeModel);
                setAllFactors(factors);

                setMultiplier(factors?.multiplier ?? 1);
                setMultiplierHorizon(
                    factors?.multiplier_horizon ?? "Forecast"
                );

                const ets = factors?.ets || {};
                setAlpha(ets?.alpha ?? 0);
                setBeta(ets?.beta ?? 0);
                setGamma(ets?.gamma ?? 0);

                if (activeModel !== "ets") {
                    const traj =
                        factors?.growth ||
                        factors?.[activeModel] ||
                        {};

                    setTotalGrowth(
                        traj?.total_growth ??
                        traj?.total_growth_pct ??
                        0
                    );

                    setDuration(traj?.duration ?? 12);

                    setTrajectoryStart(
                        traj?.trajectory_start || ""
                    );

                    setKValue(
                        traj?.k_value ??
                        traj?.k ??
                        1
                    );
                }

                setAllMetricsData(data?.metrics_data || {});

                const selectedMetricData =
                    data?.metrics_data?.[defaultFilter.metric];

                setChartData(selectedMetricData?.chart || null);
                setTableData(selectedMetricData?.table || []);
            } else {
                setFilterOptions({
                    indications: [],
                    metric_filters: resData?.metric_filters || [],
                    scenario_names: resData?.scenario_names || [],
                });
            }
        } catch (error) {
            console.error("Failed to fetch metric filters", error);
            showSnackbar("Failed to fetch metric filters", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleApplyFilter = async () => {
        const payload = {
            ta_name: therapyArea,
            scenario_name: scenarioSelector,
            indications: indication ? [indication] : [],
            lots: lot ? [lot] : [],
            metric_filter: metric,
            product: metric === "market_share" ? brand : "",
        };

        try {
            setLoading(true);
            const response = await applyMetricFilters(payload);
            const data = response?.data;

            setAppliedLot(lot);
            setAppliedBrand(brand);

            const factors = data?.factors || {};
            const activeModel = factors?.active_model || "ets";

            setModelSelection(activeModel);
            setAllFactors(factors);

            // const ets = data?.factors?.ets || {};
            // const trajectory = data?.factors?.trajectory || {};

            setMultiplier(factors?.multiplier ?? 1);
            setMultiplierHorizon(factors?.multiplier_horizon ?? "Forecast");

            const ets = factors?.ets || {};
            setAlpha(ets?.alpha ?? 0);
            setBeta(ets?.beta ?? 0);
            setGamma(ets?.gamma ?? 0);

            if (activeModel !== "ets") {
                const traj = factors?.growth || factors?.[activeModel] || {};
                console.log("----->", traj)

                setTotalGrowth(
                    traj?.total_growth ??
                    traj?.total_growth_pct ??
                    0
                );

                setDuration(traj?.duration ?? 12);

                setTrajectoryStart(
                    traj?.trajectory_start || ""
                );

                setKValue(
                    traj?.k_value ??
                    traj?.k ??
                    1
                );
            }

            // store both metrics (important for save scenario)
            setAllMetricsData(data?.metrics_data || {});

            // show only selected metric in UI
            const selectedMetricData = data?.metrics_data?.[metric];

            setChartData(selectedMetricData?.chart || null);
            setTableData(selectedMetricData?.table || []);

            // setTrajectoryStart(
            //     trajectory?.trajectory_start ||
            //     selectedMetricData?.chart?.months?.[
            //     selectedMetricData?.chart?.forecast_start_index
            //     ] ||
            //     ""
            // );
            setEditable(false);
            showSnackbar("Filters applied successfully", "success");
        } catch (error) {
            console.error("Failed to apply metric filters", error);
            showSnackbar("Failed to apply metric filters", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleRecalculate = async () => {
        let modelFactors = {};

        if (modelSelection === "ets") {
            modelFactors = {
                ets: {
                    alpha,
                    beta,
                    gamma
                }
            };
        } else {
            const growthPayload = {
                total_growth: totalGrowth,
                duration,
                trajectory_start: trajectoryStart
            };

            // only non-linear models need k
            if (modelSelection !== "linear") {
                growthPayload.k_value = Number(kValue);
            }

            modelFactors = {
                growth: growthPayload
            };
        }

        const payload = {
            ta_name: therapyArea,
            scenario_name: scenarioSelector,
            indications: indication ? [indication] : [],
            lots: lot ? [lot] : [],
            metric_filter: metric,
            product: metric === "market_share" ? brand : "",
            model_type: modelSelection,
            factors: {
                multiplier,
                multiplier_horizon: multiplierHorizon,
                ...modelFactors
            }
        };
        // console.log("growthhhh", payload)

        try {
            setLoading(true);
            const response = await recalculateMetrics(payload);
            const data = response?.data;

            const factors = data?.factors || {};
            const activeModel = factors?.active_model;

            // const ets = data?.factors?.ets || {};
            // const trajectory = data?.factors?.trajectory || {};
            setAllFactors(factors);

            setMultiplier(factors?.multiplier ?? 1);
            setMultiplierHorizon(factors?.multiplier_horizon ?? "Forecast");

            // setEtsFactors(ets);
            // setTrajectoryFactors(trajectory);
            if (activeModel === "ets") {
                const ets = factors?.ets || {};
                setAlpha(ets.alpha ?? 0);
                setBeta(ets.beta ?? 0);
                setGamma(ets.gamma ?? 0);
            } else {
                const traj = factors?.growth || factors?.[activeModel] || {};

                setTotalGrowth(
                    traj?.total_growth ??
                    traj?.total_growth_pct ??
                    0
                );

                setDuration(traj?.duration ?? 12);

                setTrajectoryStart(
                    traj?.trajectory_start || ""
                );

                setKValue(
                    traj?.k_value ??
                    traj?.k ??
                    1
                );
            }

            // update chart and table
            setAllMetricsData(data?.metrics_data || {});

            const selectedMetricData = data?.metrics_data?.[metric];

            setChartData(selectedMetricData?.chart || null);
            setTableData(selectedMetricData?.table || []);

            // setEditable(false);
            showSnackbar("Metrics recalculated successfully", "success");
        } catch (error) {
            console.error("Failed to recalculate metrics", error);
            showSnackbar("Failed to recalculate metrics", "error");
        } finally {
            setLoading(false);
        }
    };


    //  Dynamic values
    const availableLots =
        scenarioSelector && indication
            ? Object.keys(mappingData?.[scenarioSelector]?.[indication] || {})
            : [];

    const availableBrands =
        scenarioSelector && indication && lot
            ? mappingData?.[scenarioSelector]?.[indication]?.[lot] || []
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

    const recalculateInputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "100px",
        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
        },
    };

    const trajectoryMonthOptions =
        chartData?.months?.slice(
            chartData?.forecast_start_index
        ) || [];

    const handleUpdateScenario = async () => {
        if (!scenarioSelector) {
            alert("Please select a scenario to update");
            return;
        }

        if (!chartData || !tableData.length) {
            alert("No data to update");
            return;
        }

        const payload = {
            scenario_name: scenarioSelector,

            ta_name: therapyArea,
            indication,
            metric,
            product: brand || null,
            lot,

            model_type: modelSelection,

            factors: {
                multiplier,
                multiplier_horizon: multiplierHorizon,

                ets: {
                    alpha,
                    beta,
                    gamma
                },

                linear: {
                    total_growth: totalGrowth,
                    duration,
                    trajectory_start: trajectoryStart
                },
                exponential: {
                    total_growth: totalGrowth,
                    duration,
                    trajectory_start: trajectoryStart,
                    k_value: Number(kValue)
                },
                logarithmic: {
                    total_growth: totalGrowth,
                    duration,
                    trajectory_start: trajectoryStart,
                    k_value: Number(kValue)
                },
                s_curve: {
                    total_growth: totalGrowth,
                    duration,
                    trajectory_start: trajectoryStart,
                    k_value: Number(kValue)
                },

                active_model: modelSelection
            },

            metrics_data: allMetricsData
        };

        try {
            setLoading(true);
            const res = await updateScenario(payload);
            const data = res?.data;

            // sync FE state with backend response
            const factors = data?.factors || {};
            setAllFactors(factors);

            setMultiplier(factors?.multiplier ?? 1);
            setMultiplierHorizon(factors?.multiplier_horizon ?? "Forecast");

            const activeModel = factors?.active_model || "ets";
            setModelSelection(activeModel);

            if (activeModel === "ets") {
                const ets = factors?.ets || {};
                setAlpha(ets.alpha ?? 0);
                setBeta(ets.beta ?? 0);
                setGamma(ets.gamma ?? 0);
            } else {
                const traj = factors?.growth || factors?.[activeModel] || {};

                setTotalGrowth(
                    traj?.total_growth ??
                    traj?.total_growth_pct ??
                    0
                );

                setDuration(traj?.duration ?? 12);
                setTrajectoryStart(traj?.trajectory_start || "");
                setKValue(traj?.k_value ?? traj?.k ?? 1);
            }

            // update metrics
            setAllMetricsData(data?.metrics_data || {});

            const selectedMetricData = data?.metrics_data?.[metric];
            setChartData(selectedMetricData?.chart || null);
            setTableData(selectedMetricData?.table || []);

            setEditable(false);

            // alert("Scenario updated successfully!");
            showSnackbar("Scenario updated successfully", "success");
        } catch (error) {
            console.error("Update scenario failed", error);
            showSnackbar("Failed to update scenario", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleSaveScenario = async (scenarioNameFromDialog) => {
        if (!scenarioNameFromDialog) {
            alert("Please enter scenario name");
            return;
        }

        if (!chartData || !tableData.length) {
            alert("No data to save");
            return;
        }

        const payload = {
            scenario_name: scenarioNameFromDialog,

            ta_name: therapyArea,
            indication,
            metric,
            product: brand || null,
            lot,
            model_type: modelSelection,

            factors: {
                multiplier,
                multiplier_horizon: multiplierHorizon,

                ets: { alpha, beta, gamma },

                linear: {
                    total_growth: totalGrowth,
                    duration,
                    trajectory_start: trajectoryStart
                },
                exponential: {
                    total_growth: totalGrowth,
                    duration,
                    trajectory_start: trajectoryStart,
                    k_value: kValue
                },
                logarithmic: {
                    total_growth: totalGrowth,
                    duration,
                    trajectory_start: trajectoryStart,
                    k_value: kValue
                },
                s_curve: {
                    total_growth: totalGrowth,
                    duration,
                    trajectory_start: trajectoryStart,
                    k_value: kValue
                },

                active_model: modelSelection
            },

            metrics_data: allMetricsData
        };

        try {
            setLoading(true);
            const res = await saveScenario(payload);
            console.log("Scenario saved:", res.data);
            showSnackbar("Scenario created successfully", "success");
            // alert("Scenario saved successfully!");
            // Re-fetch filters so new scenario appears in dropdown
            const response = await getMetricFilters(therapyArea);
            const resData = response?.data;

            const newMappingData = resData?.data || {};
            setMappingData(newMappingData);

            const newScenarioNames = resData?.scenario_names || [];

            // Update filter options but preserve current indication list for new scenario
            setFilterOptions({
                indications: Object.keys(newMappingData?.[scenarioNameFromDialog] || {}),
                metric_filters: resData?.metric_filters || [],
                scenario_names: newScenarioNames,
            });

            // Auto-select the newly saved scenario
            setScenarioSelector(scenarioNameFromDialog);

            // Keep current selections intact (don't reset)
            // indication, lot, brand, metric remain as-is so user can Apply Filter immediately
            // setScenarioName("")

        } catch (err) {
            console.error("Save scenario failed", err);
            showSnackbar("Failed to save scenario", "error");
            // alert("Failed to save scenario");
        } finally {
            setLoading(false);
        }
    };

    // const TrajectoryControls = ({ showKValue }) => (
    //     <>
    //         <Box>
    //             <Typography sx={{ mb: 1, fontSize: "14px" }}>
    //                 TOTAL GROWTH %
    //             </Typography>

    //             <TextField
    //                 type="number"
    //                 value={totalGrowth}
    //                 disabled={!editable}
    //                 onChange={(e) => setTotalGrowth(Number(e.target.value))}
    //                 inputProps={{
    //                     min: 0,
    //                     max: 100,
    //                     step: 0.1,
    //                 }}
    //                 sx={recalculateInputStyle}
    //             />
    //         </Box>

    //         <Box>
    //             <Typography sx={{ mb: 1, fontSize: "14px" }}>
    //                 DURATION (MOS)
    //             </Typography>

    //             <TextField
    //                 type="number"
    //                 value={duration}
    //                 disabled={!editable}
    //                 onChange={(e) => setDuration(Number(e.target.value))}
    //                 inputProps={{
    //                     min: 0,
    //                     max: 100,
    //                     step: 1,
    //                 }}
    //                 sx={recalculateInputStyle}
    //             />
    //         </Box>

    //         {showKValue && (
    //             <Box>
    //                 <Typography sx={{ mb: 1, fontSize: "14px" }}>
    //                     K Value
    //                 </Typography>
    //                 <TextField
    //                     type="number"
    //                     // placeholder="e.g. 1"
    //                     value={kValue}
    //                     onChange={(e) => setKValue(e.target.value)}
    //                     inputProps={{
    //                         min: 0,
    //                         max: 1,
    //                         step: 0.01,
    //                     }}
    //                     sx={recalculateInputStyle}
    //                 />
    //             </Box>
    //         )}

    //         <Box>
    //             <Typography sx={{ mb: 1, fontSize: "14px" }}>
    //                 TRAJECTORY START
    //             </Typography>

    //             <FormControl sx={recalculateInputStyle}>
    //                 <Select
    //                     value={trajectoryStart}
    //                     onChange={(e) => setTrajectoryStart(e.target.value)}
    //                     disabled={!editable}
    //                 >
    //                     {chartData?.months?.map((month) => (
    //                         <MenuItem key={month} value={month}>
    //                             {new Date(month).toLocaleDateString("en-US", {
    //                                 month: "short",
    //                                 year: "2-digit",
    //                             })}
    //                         </MenuItem>
    //                     ))}
    //                 </Select>
    //             </FormControl>
    //         </Box>
    //     </>
    // );

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

                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}> SCENARIO SELECTOR </Typography>
                            <FormControl sx={inputStyle}>
                                <Select
                                    value={scenarioSelector}
                                    onChange={(e) => {
                                        const selectedScenario = e.target.value;

                                        setScenarioSelector(selectedScenario);
                                        setIndication("");
                                        setLot("");
                                        setBrand("");

                                        setFilterOptions((prev) => ({
                                            ...prev,
                                            indications: Object.keys(mappingData?.[selectedScenario] || {}),
                                        }));

                                        setChartData(null);
                                        setTableData([]);
                                    }}
                                    displayEmpty
                                >
                                    <MenuItem value="" disabled>Select Scenario</MenuItem>

                                    {filterOptions.scenario_names.map((scenario) => (
                                        <MenuItem key={scenario} value={scenario}>
                                            {scenario}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
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
                                    disabled={!scenarioSelector}
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
                                    disabled={!indication}
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
                    {/* <Box sx={{ display: "flex", gap: 2, alignItems: "end" }} >
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
                    </Box> */}
                </Box>

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
                                            disabled={!editable}
                                        >
                                            {trajectoryMonthOptions.map((month) => (
                                                <MenuItem
                                                    key={month}
                                                    value={month}
                                                >
                                                    {new Date(month).toLocaleDateString(
                                                        "en-US",
                                                        {
                                                            month: "short",
                                                            year: "2-digit",
                                                        }
                                                    )}
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
                    updateAllMetricsData={setAllMetricsData}
                    onUpdateScenario={handleUpdateScenario}
                    onSaveScenario={handleSaveScenario}
                    scenarioSelector={scenarioSelector}
                    selectedProduct={appliedBrand}
                    selectedLot={appliedLot}
                // scenarioName={scenarioName}
                // setScenarioName={setScenarioName}
                />
            </Paper>
        </Box>
    );
}