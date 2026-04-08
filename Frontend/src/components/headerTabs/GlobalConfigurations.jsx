import React, { useState } from "react";
import { Box, Paper, Typography, FormControl, Select, MenuItem, TextField, Button, } from "@mui/material";
import { FormHelperText } from "@mui/material";
import { useSnackbarStore } from "../../stores";

export default function GlobalConfiguration() {
    const [therapyArea, setTherapyArea] = useState("");
    const [modelGranularity, setModelGranularity] = useState("");
    const [trainStartDate, setTrainStartDate] = useState("");
    const [trainEndDate, setTrainEndDate] = useState("");
    const [forecastPeriods, setForecastPeriods] = useState("");
    const [errors, setErrors] = useState({});
    const { showSnackbar } = useSnackbarStore();

    // use the below in each of the box for those 4 filters
    // const fieldBoxStyle = {
    //     width: {
    //         xs: "100%",
    //         md: "calc(50% - 12px)", // 2 per row
    //     },
    // };
    //  <Box sx={fieldBoxStyle}>
    //       <Typography

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
        }
    };

    const handleSave = () => {
        const newErrors = {};

        if (!therapyArea) newErrors.therapyArea = "Therapeutic Area is required";
        if (!trainStartDate) newErrors.trainStartDate = "Train Start Date is required";
        if (!trainEndDate) newErrors.trainEndDate = "Train End Date is required";
        if (!modelGranularity) newErrors.modelGranularity = "Model Granularity is required";
        if (!forecastPeriods) newErrors.forecastPeriods = "Forecast Periods is required";

        setErrors(newErrors);

        if (Object.keys(newErrors).length > 0) {
            showSnackbar('Please fill all required fields', 'error');
            return;
        }
        showSnackbar('Configurations saved successfully', 'success');
    };

    return (
        <Box sx={{ p: 3 }}>
            <Typography sx={{ fontSize: "24px", fontWeight: 700, color: "#0A2342" }}>
                Global Configurations
            </Typography>

            <Typography sx={{ fontSize: "16px", color: "#5B708B", mt: 1, mb: 3 }}>
                Define your model parameters and therapeutic scope.
            </Typography>

            <Paper
                sx={{ p: 3, borderRadius: "16px", boxShadow: "none", border: "1px solid #D8DEE8" }}>
                <Typography sx={{ fontSize: "16px", fontWeight: 600, color: "#64748b", mb: 1 }}>
                    THERAPEUTIC AREA
                </Typography>

                <Box
                    sx={{ display: "flex", alignItems: "center", gap: 3, flexWrap: "wrap" }}>
                    <FormControl sx={{ minWidth: 320 }}>
                        <Select
                            value={therapyArea}
                            onChange={(e) => setTherapyArea(e.target.value)}
                            sx={{ height: "40px", borderRadius: "8px", fontSize: "14px", bgcolor: '#fcfcfd' }}>
                            <MenuItem value="oncology">Oncology</MenuItem>
                            <MenuItem value="hiv">HIV</MenuItem>
                            <MenuItem value="hiv_prep">HIV Prep</MenuItem>
                            <MenuItem value="hcv">HCV</MenuItem>
                            <MenuItem value="hbv">HBV</MenuItem>
                            <MenuItem value="pbc">PBC</MenuItem>
                            <MenuItem value="hep_delta">Hep-Delta</MenuItem>
                        </Select>

                        <FormHelperText>{errors.therapyArea}</FormHelperText>
                    </FormControl>

                    <Typography sx={{ fontSize: "15px", color: "#64748b", flex: 1 }}>
                        Selecting a scope filters the Master Data and Time Horizon settings
                        for specific business units.
                    </Typography>
                </Box>
            </Paper>

            {/* Time Horizon Card */}
            <Paper
                sx={{ p: 3, borderRadius: "16px", boxShadow: "none", border: "1px solid #D8DEE8", mt: 3 }}>
                <Typography sx={{ fontSize: "18px", fontWeight: 700, color: "#0A2342", mb: 2 }}>
                    Time Horizon & Granularity
                </Typography>

                <Box
                    sx={{ display: "flex", gap: 3, mb: 3, flexWrap: "wrap" }}>

                    <Box sx={{ flex: 1, minWidth: "320px" }}>
                        <Typography sx={{ mb: 1, fontSize: "16px", fontWeight: 600, color: "#64748b" }}>
                            TRAIN START DATE
                        </Typography>

                        <TextField
                            fullWidth
                            type="date"
                            value={trainStartDate}
                            onChange={(e) => setTrainStartDate(e.target.value)}
                            size="small"
                            sx={inputStyle}
                            error={!!errors.trainStartDate}
                            helperText={errors.trainStartDate}
                        />
                    </Box>

                    <Box sx={{ flex: 1, minWidth: "320px" }}>
                        <Typography sx={{ mb: 1, fontSize: "16px", fontWeight: 600, color: "#64748b" }}>
                            TRAIN END DATE
                        </Typography>

                        <TextField
                            fullWidth
                            type="date"
                            value={trainEndDate}
                            onChange={(e) => setTrainEndDate(e.target.value)}
                            size="small"
                            sx={inputStyle}
                            error={!!errors.trainEndDate}
                            helperText={errors.trainEndDate}
                        />
                    </Box>
                </Box>

                <Box
                    sx={{ display: "flex", gap: 3, flexWrap: "wrap" }}>

                    <Box sx={{ flex: 1, minWidth: "320px" }}>
                        <Typography sx={{ mb: 1, fontSize: "16px", fontWeight: 600, color: "#64748b" }}>
                            MODEL GRANULARITY
                        </Typography>

                        <FormControl fullWidth size="small" error={!!errors.modelGranularity}>
                            <Select
                                value={modelGranularity}
                                onChange={(e) => setModelGranularity(e.target.value)}
                                sx={inputStyle}
                            >
                                <MenuItem value="monthly">Monthly</MenuItem>
                                <MenuItem value="weekly">Weekly</MenuItem>
                            </Select>
                            <FormHelperText>{errors.modelGranularity}</FormHelperText>
                        </FormControl>
                    </Box>

                    <Box sx={{ flex: 1, minWidth: "320px" }}>
                        <Typography
                            sx={{ mb: 1, fontSize: "16px", fontWeight: 600, color: "#64748b" }}>
                            FORECAST PERIODS
                        </Typography>

                        <TextField
                            fullWidth
                            value={forecastPeriods}
                            onChange={(e) => {
                                const value = e.target.value;

                                // Allow only digits
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
                    <Button variant="contained" onClick={handleSave} sx={{ backgroundColor: "#4F46E5", px: 2, py: 1, borderRadius: "10px", textTransform: "none" }}>
                        Save Configuration
                    </Button>
                </Box>
            </Paper>

            <Paper
                sx={{ p: 3, borderRadius: "16px", boxShadow: "none", border: "1px solid #D8DEE8", mt: 3 }}>
                <Typography sx={{ fontSize: "18px", fontWeight: 700, color: "#0A2342", mb: 2 }}>
                    Master Data: Add New Brands
                </Typography>
            </Paper>
        </Box>
    );
}