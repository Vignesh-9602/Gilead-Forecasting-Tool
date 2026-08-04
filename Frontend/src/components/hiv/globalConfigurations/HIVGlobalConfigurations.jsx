import React, { useState, useEffect, useContext } from "react";
import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    TextField,
    Button,
    FormHelperText,
} from "@mui/material";

import { useSnackbarStore } from "../../../stores";
import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs from "dayjs";
import { GlobalContext } from "../../../context/Provider";
import { useLoadingStore } from "../../../stores";
import { getHIVConfigurationByTherapyArea, saveHIVConfigurations } from "../../../services/apiService";

const globalConfigDateLocaleText = {
    fieldMonthPlaceholder: () => "MM",
    fieldYearPlaceholder: () => "YYYY",
};

export default function HIVGlobalConfigurations() {
    // const [therapyArea, setTherapyArea] = useState("");
    const [modelGranularity, setModelGranularity] = useState("");
    const [trainStartDate, setTrainStartDate] = useState("");
    const [trainEndDate, setTrainEndDate] = useState("");
    const [forecastPeriods, setForecastPeriods] = useState("");
    const [errors, setErrors] = useState({});
    const { showSnackbar } = useSnackbarStore();
    const [openModal, setOpenModal] = useState(false);
    const { favState } = useContext(GlobalContext);
    const therapyArea = favState?.selectedTherapyArea;
    // const [loading, setLoading] = useState(false);
    // const { setLoading } = useLoadingStore();
    const { setLoading, isLoading } = useLoadingStore();
    const [availableTrainMonths, setAvailableTrainMonths] = useState([]);

    useEffect(() => {
        if (therapyArea) {
            fetchConfigurationByTA();
        }
    }, [therapyArea]);

    const fetchConfigurationByTA = async () => {
        try {
            setLoading(true);

            const response = await getHIVConfigurationByTherapyArea(therapyArea);

            const config = response?.data?.config;

            setAvailableTrainMonths(
                response?.data?.available_train_months || []
            );

            if (config) {
                setTrainStartDate(config.train_start_date || "");
                setTrainEndDate(config.train_end_date || "");
                setModelGranularity(
                    config.model_granularity?.toLowerCase() || ""
                );
                setForecastPeriods(config.forecast_periods || "");
            } else {
                // No configuration exists yet
                setTrainStartDate("");
                setTrainEndDate("");
                setModelGranularity("");
                setForecastPeriods("");
            }
        } catch (error) {
            console.error("Failed to fetch configuration", error);

            showSnackbar(
                error?.response?.data?.detail ||
                "Failed to load configuration",
                "error"
            );

            setTrainStartDate("");
            setTrainEndDate("");
            setModelGranularity("");
            setForecastPeriods("");
            setAvailableTrainMonths([]);
        } finally {
            setLoading(false);
        }
    };

    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        fontSize: "14px",
        height: "40px",
        "& .MuiOutlinedInput-root": {
            backgroundColor: "#fcfcfd",
            borderRadius: "8px",
            fontSize: "14px",
            height: "40px",
        },
    };

    const handleSave = async () => {
        const newErrors = {};

        if (!therapyArea) newErrors.therapyArea = "Therapeutic Area is required";
        if (!trainStartDate) newErrors.trainStartDate = "Train Start Date is required";
        if (!trainEndDate) newErrors.trainEndDate = "Train End Date is required";
        if (!modelGranularity) newErrors.modelGranularity = "Model Granularity is required";
        if (!forecastPeriods) newErrors.forecastPeriods = "Forecast Periods is required";

        setErrors(newErrors);

        if (Object.keys(newErrors).length > 0) {
            showSnackbar("Please fill all required fields", "error");
            return;
        }

        const payload = {
            config: {
                ta_name: therapyArea,
                train_start_date: trainStartDate,
                train_end_date: trainEndDate,
                model_granularity: modelGranularity,
                forecast_periods: forecastPeriods,
            },
        };
        console.log(payload)

        try {
            setLoading(true);

            const response = await saveHIVConfigurations(payload);

            // console.log("Payload sent:", payload);
            // console.log("Response:", response.data);

            showSnackbar("Configurations saved successfully", "success");

            // Optional: Refresh configuration after save
            // await fetchConfigurationByTA();

        } catch (error) {
            console.error("Save configuration failed:", error);

            const errorMessage =
                error?.response?.data?.detail ||
                "Failed to save configuration";

            showSnackbar(errorMessage, "error");
        } finally {
            setLoading(false);
        }
    };
    // console.log("favstate------", favState)

    return (
        <Box sx={{ p: 3 }}>
            {/* {loading && (
                <Box
                    sx={{
                        position: "fixed",
                        top: 0,
                        left: 0,
                        width: "100vw",
                        height: "100vh",
                        backgroundColor: "rgba(255, 255, 255, 0.6)",
                        // backdropFilter: "blur(4px)",
                        zIndex: 2000,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                    }}
                >
                    <CircularProgress size={50} sx={{ color: "#4F46E5" }} />
                </Box>
            )} */}
            <Box display="flex" justifyContent="space-between" alignItems="center">
                <Typography
                    sx={{
                        fontSize: "24px",
                        fontWeight: 700,
                        color: "#0A2342",
                    }}
                >
                    Global Configurations
                </Typography>

                {/* <Button
                    variant="outlined"
                    onClick={() => setOpenModal(true)}
                    sx={{
                        borderRadius: "8px",
                        textTransform: "none",
                    }}
                >
                    Dose Configuration
                </Button> */}
            </Box>

            <Typography
                sx={{
                    fontSize: "16px",
                    color: "#5B708B",
                    mt: 1,
                    mb: 3,
                }}
            >
                Define your model parameters and therapeutic scope.
            </Typography>

            {/* Therapeutic Area Card */}
            <Paper
                sx={{
                    p: 3,
                    borderRadius: "16px",
                    boxShadow: "none",
                    border: "1px solid #D8DEE8",
                }}
            >
                <Typography
                    sx={{
                        fontSize: "16px",
                        fontWeight: 600,
                        color: "#64748b",
                        mb: 1,
                    }}
                >
                    SELECTED THERAPEUTIC AREA
                </Typography>

                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 3,
                        flexWrap: "wrap",
                    }}
                >
                    <Box
                        sx={{
                            // minWidth: 320,
                            height: 40,
                            px: 2,
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                            border: "1px solid #D8DEE8",
                            borderRadius: "8px",
                            backgroundColor: "#d7dde6",
                        }}
                    >
                        {/* Green Dot */}
                        <Box
                            sx={{
                                width: 8,
                                height: 8,
                                borderRadius: "50%",
                                backgroundColor: "#22c55e", // green
                            }}
                        />

                        <Typography>{therapyArea}</Typography>
                    </Box>

                    {/* <Typography
                        sx={{
                            fontSize: "15px",
                            color: "#64748b",
                            flex: 1,
                        }}
                    >
                        Selected therapy area controls backend configuration loading.
                    </Typography> */}
                </Box>
            </Paper>

            {/* Time Horizon Card */}
            <Paper
                sx={{
                    p: 3,
                    borderRadius: "16px",
                    boxShadow: "none",
                    border: "1px solid #D8DEE8",
                    mt: 3,
                }}
            >
                <Typography
                    sx={{
                        fontSize: "18px",
                        fontWeight: 700,
                        color: "#0A2342",
                        mb: 2,
                    }}
                >
                    Time Horizon & Granularity
                </Typography>

                <Box sx={{ display: "flex", gap: 3, mb: 3, flexWrap: "wrap" }}>
                    <Box sx={{ flex: 1, minWidth: "320px" }}>
                        <Typography sx={{ mb: 1, fontSize: "16px", fontWeight: 600, color: "#64748b" }}>
                            TRAIN START DATE
                        </Typography>

                        <LocalizationProvider dateAdapter={AdapterDayjs} localeText={globalConfigDateLocaleText}>
                            <FormControl fullWidth size="small" error={!!errors.trainStartDate}>
                                <Select
                                    value={trainStartDate}
                                    onChange={(e) => setTrainStartDate(e.target.value)}
                                    sx={inputStyle}
                                    displayEmpty
                                    MenuProps={{
                                        PaperProps: {
                                            sx: {
                                                maxHeight: 250,
                                                width: 120,
                                                "& .MuiMenuItem-root": {
                                                    minHeight: 32,
                                                    fontSize: "14px",
                                                    py: 0.5,
                                                },
                                            },
                                        },
                                    }}
                                    renderValue={(selected) =>
                                        selected
                                            ? dayjs(selected).format("MMM YY")
                                            : "Select Start Date"
                                    }
                                >
                                    {/* <MenuItem value="" disabled>
                                        Select Start Date
                                    </MenuItem> */}
                                    {availableTrainMonths.map((month) => (
                                        <MenuItem key={month} value={month}>
                                            {dayjs(month).format("MMM YY")}
                                        </MenuItem>
                                    ))}
                                </Select>
                                <FormHelperText>{errors.trainStartDate}</FormHelperText>
                            </FormControl>
                        </LocalizationProvider>
                    </Box>

                    <Box sx={{ flex: 1, minWidth: "320px" }}>
                        <Typography sx={{ mb: 1, fontSize: "16px", fontWeight: 600, color: "#64748b" }}>
                            TRAIN END DATE
                        </Typography>

                        <LocalizationProvider dateAdapter={AdapterDayjs} localeText={globalConfigDateLocaleText}>
                            <FormControl fullWidth size="small" error={!!errors.trainEndDate}>
                                <Select
                                    value={trainEndDate}
                                    onChange={(e) => setTrainEndDate(e.target.value)}
                                    sx={inputStyle}
                                    displayEmpty
                                    MenuProps={{
                                        PaperProps: {
                                            sx: {
                                                maxHeight: 250,
                                                width: 120,
                                                "& .MuiMenuItem-root": {
                                                    minHeight: 32,
                                                    fontSize: "14px",
                                                    py: 0.5,
                                                },
                                            },
                                        },
                                    }}
                                    renderValue={(selected) =>
                                        selected
                                            ? dayjs(selected).format("MMM YY")
                                            : "Select End Date"
                                    }
                                >
                                    {availableTrainMonths
                                        .filter(
                                            (month) =>
                                                dayjs(month).isAfter(trainStartDate)
                                            // || dayjs(month).isSame(trainStartDate)
                                        )
                                        .map((month) => (
                                            <MenuItem key={month} value={month}>
                                                {dayjs(month).format("MMM YY")}
                                            </MenuItem>
                                        ))}
                                </Select>
                                <FormHelperText>{errors.trainEndDate}</FormHelperText>
                            </FormControl>
                        </LocalizationProvider>
                    </Box>
                </Box>

                <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
                    <Box sx={{ flex: 1, minWidth: "320px" }}>
                        <Typography sx={{ mb: 1, fontSize: "16px", fontWeight: 600, color: "#64748b" }}>
                            MODEL GRANULARITY
                        </Typography>

                        <FormControl fullWidth size="small" error={!!errors.modelGranularity}>
                            <Select
                                value={modelGranularity}
                                onChange={(e) => setModelGranularity(e.target.value)}
                                sx={inputStyle}
                                displayEmpty
                            >
                                <MenuItem value="" disabled>
                                    Select Model Granularity
                                </MenuItem>
                                <MenuItem value="monthly">Monthly</MenuItem>
                                <MenuItem value="weekly">Weekly</MenuItem>
                            </Select>

                            <FormHelperText>{errors.modelGranularity}</FormHelperText>
                        </FormControl>
                    </Box>

                    <Box sx={{ flex: 1, minWidth: "320px" }}>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "16px",
                                fontWeight: 600,
                                color: "#64748b",
                            }}
                        >
                            FORECAST END DATE
                        </Typography>

                        <LocalizationProvider
                            dateAdapter={AdapterDayjs}
                            localeText={globalConfigDateLocaleText}
                        >
                            <DatePicker
                                views={["year", "month"]}
                                value={forecastPeriods ? dayjs(forecastPeriods) : null}
                                minDate={
                                    trainEndDate
                                        ? dayjs(trainEndDate).add(1, "month")
                                        : undefined
                                }
                                onChange={(newValue) =>
                                    setForecastPeriods(
                                        newValue
                                            ? newValue.startOf("month").format("YYYY-MM-DD")
                                            : ""
                                    )
                                }
                                format="MMM YY"
                                slotProps={{
                                    textField: {
                                        fullWidth: true,
                                        size: "small",
                                        sx: inputStyle,
                                        error: !!errors.forecastPeriods,
                                        helperText: errors.forecastPeriods,
                                    },
                                }}
                            />
                        </LocalizationProvider>
                    </Box>
                </Box>

                <Box sx={{ display: "flex", justifyContent: "flex-end", mt: 4 }}>
                    <Button
                        variant="contained"
                        onClick={handleSave}
                        disabled={isLoading}
                        sx={{
                            backgroundColor: "#4F46E5",
                            px: 2,
                            py: 1,
                            borderRadius: "10px",
                            textTransform: "none",
                        }}
                    >
                        Save Configuration
                    </Button>
                </Box>
            </Paper>
        </Box>
    );
}