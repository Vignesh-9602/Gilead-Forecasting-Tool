import React, { useContext, useEffect, useState } from "react";
import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    Checkbox,
    ListItemText,
    Button,
} from "@mui/material";
import dayjs from "dayjs";
import { GlobalContext } from "../../../context/Provider";
import HIVOutputAnalysis from "./HIVOutputAnalysis";
import { mockOutputData } from "./OutputMock";
import { getHIVOutputFilters, applyHIVOutputFilters } from "../../../services/apiService";
import { useLoadingStore, useSnackbarStore } from "../../../stores";

/**
 * HIVOutput.jsx
 *
 * Starter component for the Output screen.
 * This contains the complete filter section only.
 * Remaining output widgets/charts/tables can be added below.
 */

export default function HIVOutput() {
    const { favState } = useContext(GlobalContext);

    const therapyArea =
        favState?.selectedTherapyArea || "HIV Treatment";

    const [availableScenarios, setAvailableScenarios] = useState([]);
    const [availableMonths, setAvailableMonths] = useState([]);
    const [availableMarkets, setAvailableMarkets] = useState([]);
    const [availableProducts, setAvailableProducts] = useState([]);

    const [selectedScenarios, setSelectedScenarios] = useState([]);
    const [selectedMarkets, setSelectedMarkets] = useState([]);
    const [selectedProducts, setSelectedProducts] = useState([]);

    const [fromDate, setFromDate] = useState("");
    const [toDate, setToDate] = useState("");

    const [outputAnalysis, setOutputAnalysis] = useState(null);

    const { showSnackbar } = useSnackbarStore();
    const { setLoading } = useLoadingStore();

    // const [selectedMetric, setSelectedMetric] =
    //     useState("market_volume");

    // const [selectedView, setSelectedView] =
    //     useState("monthly");

    useEffect(() => {
        if (therapyArea) {
            fetchFilters();
        }
    }, [therapyArea]);

    const fetchFilters = async () => {

        try {

            setLoading(true);

            const { data } = await getHIVOutputFilters(
                therapyArea
            );

            setAvailableScenarios(
                data.available_scenarios || []
            );

            setAvailableMonths(
                data.available_months || []
            );

            setAvailableMarkets(
                data.markets || []
            );

            setAvailableProducts(
                data.products || []
            );

            const filter =
                data.selected_filter || {};

            setSelectedScenarios(
                filter.scenario_names || []
            );

            setSelectedMarkets(
                filter.markets || []
            );

            setSelectedProducts(
                filter.products || []
            );

            setFromDate(
                filter.start_date || ""
            );

            setToDate(
                filter.end_date || ""
            );

            const payload = {
                ta_name: therapyArea,
                selected_filter: {
                    scenario_names: filter.scenario_names || [],
                    start_date: filter.start_date || "",
                    end_date: filter.end_date || "",
                    markets: filter.markets || [],
                    products: filter.products || [],
                },
            };

            const response = await applyHIVOutputFilters(payload);

            setOutputAnalysis(response.data.output_tabs || null);

        } catch (error) {

            console.error(
                "Failed to load output filters",
                error
            );
            showSnackbar(
                "Failed to fetch market event filters",
                "error"
            );

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
                    scenario_names: selectedScenarios,
                    start_date: fromDate,
                    end_date: toDate,
                    markets: selectedMarkets,
                    products: selectedProducts,
                },
            };

            const { data } = await applyHIVOutputFilters(payload);

            setOutputAnalysis(data.output_tabs || null);
            showSnackbar(
                "Filters applied successfully",
                "success"
            );
        } catch (error) {
            console.error("Failed to apply output filters", error);
            showSnackbar(
                "Failed to apply output filters",
                "error"
            );
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

    const labelStyle = {
        mb: 1,
        fontSize: "14px",
        fontWeight: 700,
        color: "#64748b",
    };

    const renderMultiSelect = (
        label,
        options,
        value,
        setValue
    ) => (
        <Box>
            <Typography sx={labelStyle}>{label}</Typography>

            <FormControl sx={inputStyle}>
                <Select
                    multiple
                    value={value}
                    renderValue={(selected) => selected.join(", ")}
                    onChange={(e) => {
                        const val = e.target.value;

                        if (val.includes("SELECT_ALL")) {
                            setValue(
                                value.length === options.length
                                    ? []
                                    : options
                            );
                        } else {
                            setValue(val);
                        }
                    }}
                >
                    <MenuItem value="SELECT_ALL">
                        <Checkbox
                            checked={
                                options.length > 0 &&
                                value.length === options.length
                            }
                            indeterminate={
                                value.length > 0 &&
                                value.length < options.length
                            }
                        />
                        <ListItemText primary="Select All" />
                    </MenuItem>

                    {options.map((item) => (
                        <MenuItem key={item} value={item}>
                            <Checkbox checked={value.includes(item)} />
                            <ListItemText primary={item} />
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>
        </Box>
    );

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
                    <Box>
                        <Typography sx={labelStyle}>
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
                                minWidth: "170px",
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

                    {renderMultiSelect(
                        "SCENARIO NAME",
                        availableScenarios,
                        selectedScenarios,
                        setSelectedScenarios
                    )}

                    <Box>
                        <Typography sx={labelStyle}>FROM DATE</Typography>

                        <FormControl sx={inputStyle}>
                            <Select
                                value={fromDate}
                                onChange={(e) =>
                                    setFromDate(e.target.value)
                                }
                                renderValue={(v) =>
                                    v ? dayjs(v).format("MMM YY") : ""
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
                                    <MenuItem key={month} value={month}>
                                        {dayjs(month).format("MMM YY")}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    <Box>
                        <Typography sx={labelStyle}>TO DATE</Typography>

                        <FormControl sx={inputStyle}>
                            <Select
                                value={toDate}
                                onChange={(e) =>
                                    setToDate(e.target.value)
                                }
                                renderValue={(v) =>
                                    v ? dayjs(v).format("MMM YY") : ""
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
                                    .filter(
                                        (m) =>
                                            !fromDate ||
                                            dayjs(m).isAfter(fromDate) ||
                                            dayjs(m).isSame(fromDate)
                                    )
                                    .map((month) => (
                                        <MenuItem key={month} value={month}>
                                            {dayjs(month).format("MMM YY")}
                                        </MenuItem>
                                    ))}
                            </Select>
                        </FormControl>
                    </Box>

                    {renderMultiSelect(
                        "CHANNEL",
                        availableMarkets,
                        selectedMarkets,
                        setSelectedMarkets
                    )}

                    {renderMultiSelect(
                        "PRODUCT",
                        availableProducts,
                        selectedProducts,
                        setSelectedProducts
                    )}

                    <Button
                        variant="contained"
                        onClick={handleApplyFilter}
                        sx={{
                            height: "35px",
                            borderRadius: "8px",
                            textTransform: "none",
                            backgroundColor: "#4F46E5",
                        }}
                    >
                        Apply Filter
                    </Button>
                </Box>
            </Paper>
            {outputAnalysis && (
                <HIVOutputAnalysis
                    outputAnalysis={outputAnalysis}
                    selectedMarket={selectedMarkets?.[0]}
                    selectedProduct={selectedProducts?.[0]}
                />
            )}
        </Box>
    );
}
