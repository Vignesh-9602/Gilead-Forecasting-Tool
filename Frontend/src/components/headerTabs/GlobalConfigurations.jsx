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

import { useSnackbarStore } from "../../stores";
import AverageVialsModal from "./AvgVialsDialog";
import {
    saveConfigurations,
    getConfigurationByTherapyArea,
} from "../../services/apiService";
import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs from "dayjs";
import { GlobalContext } from "../../context/Provider";
import { useLoadingStore } from "../../stores";

const globalConfigDateLocaleText = {
    fieldMonthPlaceholder: () => "MM",
};


export default function GlobalConfiguration() {
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

    useEffect(() => {
        if (therapyArea) {
            fetchConfigurationByTA(therapyArea);
        }
    }, [therapyArea]);

    const fetchConfigurationByTA = async (taName) => {
        try {
            setLoading(true);
            const response = await getConfigurationByTherapyArea(taName);

            const config = response?.data?.config;

            if (config) {
                setTrainStartDate(config.train_start_date || "");
                setTrainEndDate(config.train_end_date || "");
                setModelGranularity(config.model_granularity?.toLowerCase() || "");
                setForecastPeriods(config.forecast_periods?.toString() || "");
            }
        } catch (error) {
            console.error("No existing configuration found", error);

            setTrainStartDate("");
            setTrainEndDate("");
            setModelGranularity("");
            setForecastPeriods("");
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
                forecast_periods: Number(forecastPeriods),
            },
        };

        try {
            setLoading(true);
            await saveConfigurations(payload);

            showSnackbar("Configurations saved successfully", "success");

            console.log("Payload sent:", payload);
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
    console.log("favstate------", favState)

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
                            <DatePicker
                                value={trainStartDate ? dayjs(trainStartDate) : null}
                                onChange={(newValue) =>
                                    setTrainStartDate(newValue ? newValue.format("YYYY-MM-DD") : "")
                                }
                                format="DD-MMM-YYYY"
                                slotProps={{
                                    textField: {
                                        fullWidth: true,
                                        size: "small",
                                        sx: inputStyle,
                                        error: !!errors.trainStartDate,
                                        helperText: errors.trainStartDate,
                                    },
                                }}
                            />
                        </LocalizationProvider>
                    </Box>

                    <Box sx={{ flex: 1, minWidth: "320px" }}>
                        <Typography sx={{ mb: 1, fontSize: "16px", fontWeight: 600, color: "#64748b" }}>
                            TRAIN END DATE
                        </Typography>

                        <LocalizationProvider dateAdapter={AdapterDayjs} localeText={globalConfigDateLocaleText}>
                            <DatePicker
                                value={trainEndDate ? dayjs(trainEndDate) : null}
                                onChange={(newValue) =>
                                    setTrainEndDate(newValue ? newValue.format("YYYY-MM-DD") : "")
                                }
                                format="DD-MMM-YYYY"
                                maxDate={dayjs()}
                                slotProps={{
                                    textField: {
                                        fullWidth: true,
                                        size: "small",
                                        sx: inputStyle,
                                        error: !!errors.trainEndDate,
                                        helperText: errors.trainEndDate,
                                    },
                                }}
                            />
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
                        <Typography sx={{ mb: 1, fontSize: "16px", fontWeight: 600, color: "#64748b" }}>
                            FORECAST PERIODS
                        </Typography>

                        <TextField
                            fullWidth
                            value={forecastPeriods}
                            onChange={(e) => {
                                const value = e.target.value;
                                if (/^\d*$/.test(value)) {
                                    setForecastPeriods(value);
                                }
                            }}
                            size="small"
                            placeholder="eg. 36"
                            sx={inputStyle}
                            error={!!errors.forecastPeriods}
                            helperText={errors.forecastPeriods}
                        />
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

            <AverageVialsModal
                open={openModal}
                onClose={() => setOpenModal(false)}
                therapyArea={therapyArea}
            />
        </Box>
    );
}