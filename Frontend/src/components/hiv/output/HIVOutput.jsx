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

    const outputFilterMock = {
        ta_name: "HIV Treatment",

        available_scenarios: [
            "BASE",
            "Test Scenario",
            "Scenario 2",
        ],

        markets: [
            "Retail",
            "Non-retail",
        ],

        products: [
            "Truvada",
            "Descovy",
            "Biktarvy",
        ],

        available_months: [
            "2024-06-01",
            "2024-07-01",
            "2024-08-01",
            "2024-09-01",
            "2024-10-01",
            "2024-11-01",
            "2024-12-01",
            "2025-01-01",
            "2025-02-01",
            "2025-03-01",
            "2025-04-01",
            "2025-05-01",
            "2025-06-01",
            "2025-07-01",
            "2025-08-01",
            "2025-09-01",
            "2025-10-01",
            "2025-11-01",
            "2025-12-01",
            "2026-01-01",
            "2026-02-01",
            "2026-03-01",
            "2026-04-01",
            "2026-05-01",
            "2026-06-01",
            "2026-07-01",
            "2026-08-01",
            "2026-09-01",
            "2026-10-01",
            "2026-11-01",
            "2026-12-01",
        ],

        selected_filter: {
            scenario_names: ["BASE"],
            markets: ["Retail"],
            products: ["Truvada"],
            start_date: "2024-06-01",
            end_date: "2026-12-01",
        },
    };

    useEffect(() => {
        if (therapyArea) {
            fetchFilters();
        }
    }, [therapyArea]);

    const fetchFilters = () => {

        const response = outputFilterMock;

        setAvailableScenarios(
            response.available_scenarios || []
        );

        setAvailableMonths(
            response.available_months || []
        );

        setAvailableMarkets(
            response.markets || []
        );

        setAvailableProducts(
            response.products || []
        );

        const filter =
            response.selected_filter || {};

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

    };

    const handleApplyFilter = () => {
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

        console.log(payload);

        setOutputAnalysis(
            mockOutputData.output_tabs
        );
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

                    {renderMultiSelect(
                        "MARKET",
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
