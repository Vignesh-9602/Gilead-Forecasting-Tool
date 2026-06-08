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
    Dialog,
    DialogTitle,
    DialogContent,
    DialogContentText,
    DialogActions,
} from "@mui/material";

import { GlobalContext } from "../../../context/Provider";
import { getScenarioFilters, applyScenarioFilters, saveScenarioSelection, finalizeScenarios, getScenarioStatus, clearStatus } from "../../../services/apiService";
import ScenarioChart from "./ScenarioChart";
import ScenarioTable from "./ScenarioTable";
import { useSnackbarStore, useLoadingStore } from "../../../stores";

export default function Scenarios() {
    const { favState } = useContext(GlobalContext);
    const therapyArea = favState?.selectedTherapyArea;

    const [indication, setIndication] = useState("");
    const [lot, setLot] = useState("");
    // const [metric, setMetric] = useState("");
    // const [brand, setBrand] = useState("");
    const [compareScenarios, setCompareScenarios] = useState([]);
    const [finalizationStatus, setFinalizationStatus] = useState({});
    const [canFinalize, setCanFinalize] = useState(false);
    const { showSnackbar } = useSnackbarStore();
    const [isDataLoaded, setIsDataLoaded] = useState(false);
    const [tableMetric, setTableMetric] = useState("nps");

    const [mappingData, setMappingData] = useState({});
    const [filterOptions, setFilterOptions] = useState({
        indications: [],
        metric_filters: [],
    });

    const [chartData, setChartData] = useState(null);
    const [tableData, setTableData] = useState({});

    const [openResetDialog, setOpenResetDialog] = useState(false);
    const { setLoading, isLoading } = useLoadingStore();

    useEffect(() => {
        if (therapyArea) {
            fetchScenarioFilters();
        }
    }, [therapyArea]);

    const metric = "nps";

    useEffect(() => {
        if (!therapyArea || !indication || !metric) return;

        fetchScenarioStatus();
    }, [therapyArea, indication]);

    useEffect(() => {
        setChartData(null);
        setTableData([]);
        setTableMetric("nps");
        setIsDataLoaded(false);
    }, [indication]);

    // Auto-select all scenarios when lot changes
    useEffect(() => {
        if (indication && lot && mappingData[indication]?.[lot]?.available_scenarios) {
            const allScenarioIds = mappingData[indication][lot].available_scenarios.map(sc => sc.scenario_id);
            setCompareScenarios(allScenarioIds);
        }
    }, [lot, indication, mappingData]);

    const fetchScenarioStatus = async () => {
        try {
            const payload = {
                ta_name: therapyArea,
                indication,
                metric: "nps",
            };

            const response = await getScenarioStatus(payload);
            const data = response?.data;

            setFinalizationStatus(data.finalization_status || {});
            setCanFinalize(data.can_finalize);

        } catch (error) {
            console.error("Failed to fetch scenario status", error);

            // fallback → show all pending
            setFinalizationStatus({});
            setCanFinalize(false);
        }
    };


    const fetchScenarioFilters = async () => {
        try {
            setLoading(true);
            const response = await getScenarioFilters(therapyArea);
            const resData = response?.data;

            setMappingData(resData?.data || {});

            const defaultFilter = resData?.selected_filter;

            setFilterOptions({
                indications: Object.keys(resData?.data || {}),
                metric_filters: resData?.metric_filters || [],
            });

            if (defaultFilter) {
                setIndication(defaultFilter.indication);
                setLot(defaultFilter.lot);

                // Auto Apply Filter
                const scenarioNames =
                    resData?.data?.[
                        defaultFilter.indication
                    ]?.[
                        defaultFilter.lot
                    ]?.available_scenarios?.map(
                        sc => sc.scenario_name
                    ) || [];

                const payload = {
                    ta_name: therapyArea,
                    indication: defaultFilter.indication,
                    lot: defaultFilter.lot,
                    metric: "nps",
                    scenario_names: scenarioNames,
                };

                const applyResponse =
                    await applyScenarioFilters(payload);

                const data = applyResponse?.data;

                setChartData(data?.chart || null);
                setTableData(data?.table || {});
                setIsDataLoaded(true);
            }

        } catch (error) {
            console.error(
                "Failed to fetch scenario filters",
                error
            );

            showSnackbar(
                "Failed to fetch scenario filters",
                "error"
            );
        } finally {
            setLoading(false);
        }
    };

    const handleApply = async () => {
        if (!therapyArea || !indication || !lot) return;

        const payload = {
            ta_name: therapyArea,
            indication,
            lot,
            metric: "nps",
            scenario_names: availableScenarios
                .filter(sc => compareScenarios.includes(sc.scenario_id))
                .map(sc => sc.scenario_name),
            // product: metric === "market_share" ? brand : ""
        };

        try {
            setLoading(true);
            const response = await applyScenarioFilters(payload);

            const data = response?.data;

            // DIRECT ASSIGN (no transformation needed)
            setChartData(data.chart);
            setTableData(data.table);
            setIsDataLoaded(true);
            showSnackbar("Filters applied successfully", "success");
        } catch (error) {
            console.error("Apply filter failed", error);
            showSnackbar("Failed to apply filter", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleSaveScenario = async (selectedScenario) => {
        if (!selectedScenario) return;

        const payload = {
            ta_name: therapyArea,
            indication,
            lot,
            metric: "nps",
            scenario_name: selectedScenario,
        };

        try {
            setLoading(true);
            const response = await saveScenarioSelection(payload);
            const data = response?.data;

            console.log("Saved:", data);

            // Update UI
            setFinalizationStatus(data.finalization_status || {});
            setCanFinalize(data.can_finalize);
            showSnackbar(`Scenario saved successfully for ${lot}`, "success");

        } catch (error) {
            console.error("Save scenario failed", error);
            showSnackbar("Failed to save scenario", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleFinalizeScenarios = async () => {
        if (!therapyArea || !indication) return;

        const payload = {
            ta_name: therapyArea,
            indication,
            metric: "nps",
        };

        try {
            setLoading(true);
            const response = await finalizeScenarios(payload);
            const data = response?.data;

            console.log("Finalized:", data);

            //  Map backend response to your UI format
            const mappedStatus = {};

            Object.entries(data.finalized_selections || {}).forEach(
                ([lotKey, value]) => {
                    mappedStatus[lotKey] = {
                        finalized: true,
                        scenario_name: value?.scenario_name,
                    };
                }
            );

            // Update UI state
            setFinalizationStatus(mappedStatus);
            setCanFinalize(false);
            showSnackbar("Scenarios finalized successfully", "success");

        } catch (error) {
            console.error("Finalize failed", error);
            showSnackbar("Failed to finalize scenarios", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleResetStatus = async () => {
        try {
            setLoading(true);
            const payload = {
                ta_name: therapyArea,
                indication,
                metric: "nps",
            };

            const response = await clearStatus(payload);

            const data = response?.data;

            setFinalizationStatus(data.finalization_status || {});
            setCanFinalize(false);

            setOpenResetDialog(false);

            showSnackbar(
                "Selected scenarios were cleared successfully",
                "success"
            );

        } catch (error) {
            console.error("Reset status failed", error);

            showSnackbar(
                "Failed to reset scenario status",
                "error"
            );
        } finally {
            setLoading(false);
        }
    };

    const availableLots = indication
        ? Object.keys(mappingData[indication] || {})
        : [];

    // const availableProducts =
    //     indication && lot
    //         ? mappingData[indication]?.[lot]?.products || []
    //         : [];

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

    const handleSelectAllScenarios = () => {
        const allScenarioIds = availableScenarios.map(sc => sc.scenario_id);
        const isAllSelected = compareScenarios.length === availableScenarios.length;

        if (isAllSelected) {
            // If all are selected, deselect all
            setCompareScenarios([]);
        } else {
            // Select all
            setCompareScenarios(allScenarioIds);
        }
    };

    const handleCompareScenarioChange = (event) => {
        const { value } = event.target;

        // Check if "SELECT_ALL" option was selected
        if (value.includes("SELECT_ALL")) {
            const allScenarioIds = availableScenarios.map(sc => sc.scenario_id);

            // If all are selected, deselect all; otherwise select all
            if (compareScenarios.length === availableScenarios.length) {
                setCompareScenarios([]);
            } else {
                setCompareScenarios(allScenarioIds);
            }
        } else {
            // Normal scenario selection
            setCompareScenarios(value);
        }
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
                                    // setBrand("");
                                    // setCompareScenarios([]);
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
                    {/* <Box>
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
                    </Box> */}

                    {/* Compare Scenarios */}
                    <Box>
                        <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                            COMPARE SCENARIOS
                        </Typography>

                        <FormControl sx={{ ...inputStyle, maxWidth: 220 }}>
                            <Select
                                multiple
                                value={compareScenarios}
                                onChange={handleCompareScenarioChange}
                                renderValue={(selected) =>
                                    availableScenarios
                                        .filter((sc) => selected.includes(sc.scenario_id))
                                        .map((sc) => sc.scenario_name)
                                        .join(", ")
                                }
                            >
                                <MenuItem value="SELECT_ALL">
                                    <Checkbox
                                        checked={compareScenarios.length === availableScenarios.length && availableScenarios.length > 0}
                                        indeterminate={compareScenarios.length > 0 && compareScenarios.length < availableScenarios.length}
                                    />
                                    <ListItemText primary="Select All" sx={{ fontWeight: 700 }} />
                                </MenuItem>
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
                            justifyContent: "space-between",
                            // gap: 6,
                            flexWrap: "wrap",
                        }}
                    >
                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                gap: 4,
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

                            {availableLots.map((lotKey) => {
                                const lotData = finalizationStatus?.[lotKey];

                                const isFinalized = lotData?.finalized || false;
                                const scenarioName = lotData?.scenario_name;

                                return (
                                    <Box
                                        key={lotKey}
                                        sx={{ display: "flex", alignItems: "center", gap: 1 }}
                                    >
                                        {/* Status dot */}
                                        <Box
                                            sx={{
                                                width: 12,
                                                height: 12,
                                                borderRadius: "50%",
                                                backgroundColor: isFinalized ? "#10b981" : "#f59e0b",
                                            }}
                                        />

                                        {/* Text */}
                                        <Typography
                                            sx={{
                                                fontSize: "16px",
                                                fontWeight: isFinalized ? 700 : 600,
                                                color: isFinalized ? "#10b981" : "#000",
                                            }}
                                        >
                                            {lotKey}: {scenarioName || "Pending"}
                                        </Typography>
                                    </Box>
                                );
                            })}
                        </Box>
                        <Box sx={{ display: "flex", gap: 2 }}>
                            <Button
                                variant="outlined"
                                disabled={!isDataLoaded}
                                onClick={() => setOpenResetDialog(true)}
                                sx={{
                                    minWidth: "80px",
                                    height: "42px",
                                    borderRadius: "10px",
                                    textTransform: "none",
                                }}
                            >
                                Reset
                            </Button>
                            <Button
                                variant="contained"
                                disabled={!canFinalize || !isDataLoaded}
                                onClick={handleFinalizeScenarios}
                                sx={{
                                    minWidth: "220px",
                                    height: "42px",
                                    borderRadius: "10px",
                                    textTransform: "none",
                                    backgroundColor: "#0f172a",
                                    whiteSpace: "nowrap",
                                }}
                            >
                                Finalize All Scenarios
                            </Button>
                        </Box>
                    </Box>
                </Paper>
                <ScenarioChart chartData={chartData} />
                <ScenarioTable
                    chartData={chartData}
                    tableData={tableData?.[tableMetric] || []}
                    tableMetric={tableMetric}
                    setTableMetric={setTableMetric}
                    selectedLot={lot}
                    indication={indication}
                    onSaveSelection={handleSaveScenario}
                />
                <Dialog
                    open={openResetDialog}
                    onClose={() => setOpenResetDialog(false)}
                >
                    <DialogTitle>
                        Reset Finalization Status
                    </DialogTitle>

                    <DialogContent>
                        <DialogContentText>
                            Are you sure you want to reset all saved
                            scenarios?
                        </DialogContentText>
                    </DialogContent>

                    <DialogActions>
                        <Button
                            onClick={() => setOpenResetDialog(false)}
                        >
                            Cancel
                        </Button>

                        <Button
                            color="error"
                            variant="contained"
                            onClick={handleResetStatus}
                        >
                            Reset
                        </Button>
                    </DialogActions>
                </Dialog>
            </Paper >
        </Box >
    );
}