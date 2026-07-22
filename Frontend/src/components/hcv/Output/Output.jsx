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
import OutputAnalysis from "./OutputAnalysis";
// Adjust this path to wherever apiService.js actually lives relative to this file.
import { getLiverOutputFilters, applyLiverOutputFilters } from "../../../services/apiService";

const TA_NAME = "HCV";

/**
 * Output.jsx
 *
 * Starter component for the Output screen.
 * This contains the complete filter section only.
 * Remaining output widgets/charts/tables can be added below.
 */

export default function Output() {
    const { favState } = useContext(GlobalContext);

    const therapyArea =
        favState?.selectedTherapyArea || "HCV Treatment";

    const [availableScenarios, setAvailableScenarios] = useState([]);
    const [availableMonths, setAvailableMonths] = useState([]);
    const [availablePayers, setAvailablePayers] = useState([]);
    const [availableProducts, setAvailableProducts] = useState([]);

    const [selectedScenarios, setSelectedScenarios] = useState([]);
    const [selectedPayers, setSelectedPayers] = useState([]);
    const [selectedProducts, setSelectedProducts] = useState([]);

    const [fromDate, setFromDate] = useState("");
    const [toDate, setToDate] = useState("");

    const [outputAnalysis, setOutputAnalysis] = useState(null);
    const [isLoadingFilters, setIsLoadingFilters] = useState(false);
    const [isApplyingFilters, setIsApplyingFilters] = useState(false);

    useEffect(() => {
        initOutputScreen();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Loads the filter options, then immediately runs apply-filters once
    // with whatever the API returned as the default selection, so the
    // screen has data on first load without the user clicking "Apply Filter".
    const initOutputScreen = async () => {
        setIsLoadingFilters(true);

        try {
            const { data } = await getLiverOutputFilters(TA_NAME);

            setAvailableScenarios(data?.available_scenarios || []);
            setAvailableMonths(data?.available_months || []);
            setAvailablePayers(data?.payers || []);
            setAvailableProducts(data?.products || []);

            const filter = data?.selected_filter || {};

            setSelectedScenarios(filter.scenario_names || []);
            setSelectedPayers(filter.payers || []);
            setSelectedProducts(filter.products || []);
            setFromDate(filter.start_date || "");
            setToDate(filter.end_date || "");

            await fetchOutputAnalysis({
                scenario_names: filter.scenario_names || [],
                payers: filter.payers || [],
                products: filter.products || [],
                start_date: filter.start_date || "",
                end_date: filter.end_date || "",
            });
        } catch (err) {
            console.error("Failed to load output filters", err);
        } finally {
            setIsLoadingFilters(false);
        }
    };

    const fetchOutputAnalysis = async ({
        scenario_names,
        payers,
        products,
        start_date,
        end_date,
    }) => {
        const payload = {
            ta: TA_NAME,
            scenario_names,
            payers,
            products,
            start_date,
            end_date,
            selected_metric: "payer_volume",
            selected_view: "monthly",
        };

        setIsApplyingFilters(true);

        try {
            const { data } = await applyLiverOutputFilters(payload);
            // The API wraps the tab data under "output_tabs" alongside
            // selected_filter/metric_filters/view_options — only the
            // tab-keyed object is what OutputAnalysis needs.
            setOutputAnalysis(data?.output_tabs);
        } catch (err) {
            console.error("Failed to apply output filters", err);
        } finally {
            setIsApplyingFilters(false);
        }
    };

    const handleApplyFilter = () => {
        fetchOutputAnalysis({
            scenario_names: selectedScenarios,
            payers: selectedPayers,
            products: selectedProducts,
            start_date: fromDate,
            end_date: toDate,
        });
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

    const renderSingleSelect = (
        label,
        options,
        value,
        setValue
    ) => (
        <Box>
            <Typography sx={labelStyle}>{label}</Typography>

            <FormControl sx={inputStyle}>
                <Select
                    value={value?.[0] || ""}
                    onChange={(e) =>
                        setValue(e.target.value ? [e.target.value] : [])
                    }
                >
                    {options.map((item) => (
                        <MenuItem key={item} value={item}>
                            {item}
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

                    {renderSingleSelect(
                        "PAYER",
                        availablePayers,
                        selectedPayers,
                        setSelectedPayers
                    )}

                    {renderSingleSelect(
                        "PRODUCT",
                        availableProducts,
                        selectedProducts,
                        setSelectedProducts
                    )}

                    <Button
                        variant="contained"
                        onClick={handleApplyFilter}
                        disabled={isApplyingFilters || isLoadingFilters}
                        sx={{
                            height: "35px",
                            borderRadius: "8px",
                            textTransform: "none",
                            backgroundColor: "#4F46E5",
                        }}
                    >
                        {isApplyingFilters ? "Applying..." : "Apply Filter"}
                    </Button>
                </Box>
            </Paper>
            {outputAnalysis && (
                <OutputAnalysis
                    outputAnalysis={outputAnalysis}
                    selectedPayer={selectedPayers?.[0]}
                    selectedProduct={selectedProducts?.[0]}
                />
            )}
        </Box>
    );
}