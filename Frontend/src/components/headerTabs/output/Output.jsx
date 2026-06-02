// src/components/headerTabs/output/Output.jsx

import React, { useContext, useState } from "react";
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

import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";

import dayjs from "dayjs";

import { GlobalContext } from "../../../context/Provider";

const outputDateLocaleText = {
    fieldMonthPlaceholder: () => "MM",
};

const indicationOptions = [
    "mTNBC",
    "mHR+",
];

const productOptions = [
    "Trodelvy",
    "TPC",
];

const metricOptions = [
    "New Patient Starts",
    "Total Patient Counts",
    "Demand Vial Split",
    "Net Demand Revenue",
];

export default function Output() {
    const { favState } = useContext(GlobalContext);

    const therapyArea = favState?.selectedTherapyArea;

    const [indications, setIndications] = useState([]);
    const [products, setProducts] = useState([]);
    const [metrics, setMetrics] = useState([]);

    const [startDate, setStartDate] = useState(null);
    const [endDate, setEndDate] = useState(null);

    const labelStyle = {
        mb: 1,
        fontSize: "14px",
        fontWeight: 700,
        color: "#64748b",
    };

    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        width: "180px",

        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
        },
    };

    const handleMultiSelect = (
        value,
        options,
        selectedValue,
        setter
    ) => {
        if (value.includes("SELECT_ALL")) {
            if (selectedValue.length === options.length) {
                setter([]);
            } else {
                setter(options);
            }
        } else {
            setter(value);
        }
    };

    const isApplyEnabled =
        indications.length > 0 &&
        products.length > 0 &&
        metrics.length > 0 &&
        startDate &&
        endDate;

    const renderMultiSelect = (
        label,
        value,
        setValue,
        options,
        placeholder
    ) => (
        <Box>
            <Typography sx={labelStyle}>
                {label}
            </Typography>

            <FormControl sx={inputStyle}>
                <Select
                    multiple
                    value={value}
                    displayEmpty
                    renderValue={(selected) =>
                        selected.length === 0
                            ? placeholder
                            : selected.join(", ")
                    }
                    onChange={(e) =>
                        handleMultiSelect(
                            e.target.value,
                            options,
                            value,
                            setValue
                        )
                    }
                >
                    <MenuItem value="SELECT_ALL">
                        <Checkbox
                            checked={
                                value.length === options.length &&
                                options.length > 0
                            }
                            indeterminate={
                                value.length > 0 &&
                                value.length < options.length
                            }
                        />
                        <ListItemText primary="Select All" />
                    </MenuItem>

                    {options.map((item) => (
                        <MenuItem
                            key={item}
                            value={item}
                        >
                            <Checkbox
                                checked={value.includes(item)}
                            />
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
                    {/* THERAPEUTIC AREA */}
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

                            <Typography>
                                {therapyArea}
                            </Typography>
                        </Box>
                    </Box>

                    {renderMultiSelect(
                        "INDICATION",
                        indications,
                        setIndications,
                        indicationOptions,
                        "Select Indication"
                    )}

                    {renderMultiSelect(
                        "PRODUCT",
                        products,
                        setProducts,
                        productOptions,
                        "Select Product"
                    )}

                    {/* START MONTH */}
                    <Box>
                        <Typography sx={labelStyle}>
                            START MONTH
                        </Typography>

                        <LocalizationProvider dateAdapter={AdapterDayjs} localeText={outputDateLocaleText}>
                            <DatePicker
                                value={startDate ? dayjs(startDate) : null}
                                onChange={(newValue) =>
                                    setStartDate(
                                        newValue
                                            ? newValue.format("YYYY-MM-DD")
                                            : ""
                                    )
                                }
                                format="DD-MMM-YYYY"
                                slotProps={{
                                    textField: {
                                        size: "small",
                                        placeholder: "DD-MM-YYYY",
                                        sx: {
                                            width: "180px",

                                            "& .MuiInputBase-input": {
                                                color: startDate
                                                    ? "#000"
                                                    : "transparent",

                                                caretColor: "transparent",
                                            },
                                        },
                                    },
                                }}
                            />
                        </LocalizationProvider>
                    </Box>

                    {/* END MONTH */}
                    <Box>
                        <Typography sx={labelStyle}>
                            END MONTH
                        </Typography>

                        <LocalizationProvider dateAdapter={AdapterDayjs} localeText={outputDateLocaleText}>
                            <DatePicker
                                value={endDate ? dayjs(endDate) : null}
                                onChange={(newValue) =>
                                    setEndDate(
                                        newValue
                                            ? newValue.format("YYYY-MM-DD")
                                            : ""
                                    )
                                }
                                format="DD-MMM-YYYY"
                                slotProps={{
                                    textField: {
                                        size: "small",
                                        placeholder: "DD-MM-YYYY",
                                        sx: {
                                            width: "180px",

                                            "& .MuiInputBase-input": {
                                                color: endDate
                                                    ? "#000"
                                                    : "transparent",

                                                caretColor: "transparent",
                                            },
                                        },
                                    },
                                }}
                            />
                        </LocalizationProvider>
                    </Box>

                    {renderMultiSelect(
                        "METRIC",
                        metrics,
                        setMetrics,
                        metricOptions,
                        "Select Metric"
                    )}

                    <Button
                        variant="contained"
                        disabled={!isApplyEnabled}
                        sx={{
                            height: "40px",
                            px: 3,
                            borderRadius: "8px",
                            textTransform: "none",
                            backgroundColor: "#4F46E5",
                        }}
                    >
                        Apply Filter
                    </Button>
                </Box>
            </Paper>
            <Paper
                sx={{
                    p: 3,
                    borderRadius: "16px",
                    border: "1px solid #D8DEE8",
                    boxShadow: "none",
                    mt: 3
                }}
            >
                Chart
            </Paper>
        </Box>
    );
}