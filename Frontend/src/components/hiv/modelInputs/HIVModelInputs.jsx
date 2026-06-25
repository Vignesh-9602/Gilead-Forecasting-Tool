import React, { useState, useContext } from "react";

import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    TextField,
    Button,
} from "@mui/material";

import Tooltip from "@mui/material/Tooltip";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

import { GlobalContext } from "../../../context/Provider";

import dayjs from "dayjs";
import HIVMarketAnalysis from "./HIVMarketAnalysis";

const globalConfigDateLocaleText = {
    fieldMonthPlaceholder: () => "MM",
    fieldYearPlaceholder: () => "YYYY",
};

const availableMonths = [
    "2024-01-01",
    "2024-02-01",
    "2024-03-01",
    "2024-04-01",
    "2024-05-01",
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
];

export default function HIVModelInput() {
    const { favState } = useContext(GlobalContext);

    const therapyArea = favState?.selectedTherapyArea || "HIV";

    // ---------------- FILTERS ----------------

    const [fromDate, setFromDate] = useState("2024-01-01");
    const [toDate, setToDate] = useState("2025-12-01");

    const [metricFilter, setMetricFilter] =
        useState("market_volume");

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
        useState(0.35);

    const [beta, setBeta] =
        useState(0.25);

    const [gamma, setGamma] =
        useState(0.65);

    const [totalGrowth, setTotalGrowth] =
        useState(15);

    const [duration, setDuration] =
        useState(12);

    const [kValue, setKValue] =
        useState(1);

    const [trajectoryStart, setTrajectoryStart] =
        useState("2025-01-01");

    const [multiplier, setMultiplier] =
        useState(1);

    const [multiplierHorizon, setMultiplierHorizon] =
        useState("Forecast");

    const handleApplyFilter = () => {
        console.log({
            therapyArea,
            fromDate,
            toDate,
            metricFilter,
            marketFilter,
            productFilter,
        });
    };

    const handleRecalculate = () => {
        console.log("Dummy Recalculate");
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

                        <Box>
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
                        </Box>

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
                                    <MenuItem value="retail">
                                        Retail
                                    </MenuItem>

                                    <MenuItem value="non-retail">
                                        Non-Retail
                                    </MenuItem>
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
                                    <MenuItem value="Truvada">
                                        Truvada
                                    </MenuItem>

                                    <MenuItem value="Descovy">
                                        Descovy
                                    </MenuItem>

                                    <MenuItem value="Biktarvy">
                                        Biktarvy
                                    </MenuItem>
                                </Select>
                            </FormControl>
                        </Box>

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
                    </Box>
                </Box>

                {/* ===================== STATISTICAL ENGINE ===================== */}

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
                                            {availableMonths.map((month) => (
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

            </Paper>
            <HIVMarketAnalysis />
        </Box >
    );
}