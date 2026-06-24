import React, { useState, useEffect, useContext } from "react";
import {
  Box,
  Paper,
  Typography,
  FormControl,
  Select,
  MenuItem,
  Button,
  FormHelperText,
  Checkbox,
  ListItemText,
} from "@mui/material";
import { useSnackbarStore } from "../../../stores";
import { useLoadingStore } from "../../../stores";
import AverageVialsModal from "../../headerTabs/AvgVialsDialog";
import {
  // generic configuration API (used for non-HCV flows)
  saveConfigurations,
  getConfigurationByTherapyArea,
  // HCV-specific API wrappers (frontend names changed to HCV)
  saveConfigurationsHCV,
  getConfigurationByTherapyAreaHCV,
} from "../../../services/apiService";
import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs from "dayjs";
import { GlobalContext } from "../../../context/Provider";

const globalConfigDateLocaleText = {
  fieldMonthPlaceholder: () => "MM",
  fieldYearPlaceholder: () => "YYYY",
};

export default function GlobalConfiguration() {
  const [modelGranularity, setModelGranularity] = useState("");
  const [trainStartDate, setTrainStartDate] = useState("");
  const [trainEndDate, setTrainEndDate] = useState("");
  const [forecastPeriods, setForecastPeriods] = useState("");
  const [payer, setPayer] = useState([]);
  const [product, setProduct] = useState([]);
  const [errors, setErrors] = useState({});
  const [openModal, setOpenModal] = useState(false);
  const [availableTrainMonths, setAvailableTrainMonths] = useState([]);

  const { showSnackbar } = useSnackbarStore();
  const { setLoading, isLoading } = useLoadingStore();
  const { favState } = useContext(GlobalContext);
  const therapyArea = favState?.selectedTherapyArea;

  // ── LOAD ON TA CHANGE ────────────────────────────────────────────────────
  useEffect(() => {
    if (therapyArea) fetchConfigurationByTA(therapyArea);
  }, [therapyArea]);

  const fetchConfigurationByTA = async (taName) => {
    try {
      setLoading(true);

      // Use HCV-specific configuration API when TA is HCV
      const response =
        taName === "HCV"
          ? await getConfigurationByTherapyAreaHCV(taName)
          : await getConfigurationByTherapyArea(taName);

      console.log("response.data:", response.data); // check actual shape

      // ── Backend returns data directly (no nested "data" key) ──
      const responseData = response?.data;
      const available_train_months = responseData?.available_train_months || [];
      const config = responseData?.config || null;

      setAvailableTrainMonths(available_train_months);

      if (config) {
        setTrainStartDate(config.train_start_date || "");
        setTrainEndDate(config.train_end_date || "");
        setModelGranularity(config.model_granularity?.toLowerCase() || "");
        setPayer(config.payer || []);
        setProduct(config.brand || []);

        // forecast_periods — backend converts integer → date string before returning
        // so it will always come back as "YYYY-MM-DD" string
        setForecastPeriods(config.forecast_periods || "");
      } else {
        resetFields();
      }
    } catch (error) {
      console.error("Failed to load configuration:", error);
      resetFields();
    } finally {
      setLoading(false);
    }
  };

  const resetFields = () => {
    setTrainStartDate("");
    setTrainEndDate("");
    setModelGranularity("");
    setForecastPeriods("");
    setPayer([]);
    setProduct([]);
  };

  // ── SAVE ─────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    const newErrors = {};
    if (!therapyArea) newErrors.therapyArea = "Therapeutic Area is required";
    if (!trainStartDate)
      newErrors.trainStartDate = "Train Start Date is required";
    if (!trainEndDate) newErrors.trainEndDate = "Train End Date is required";
    if (!modelGranularity)
      newErrors.modelGranularity = "Model Granularity is required";
    if (!forecastPeriods)
      newErrors.forecastPeriods = "Forecast End Date is required";
    if (!payer.length) newErrors.payer = "Payer is required";
    if (!product.length) newErrors.product = "Product is required";

    setErrors(newErrors);
    if (Object.keys(newErrors).length > 0) {
      showSnackbar("Please fill all required fields", "error");
      return;
    }

    const payload = {
      config: {
        ta_name: therapyArea,
        payer: payer,
        brand: product, // state "product" → API field "brand"
        train_start_date: trainStartDate,
        train_end_date: trainEndDate,
        model_granularity: modelGranularity,
        forecast_periods: forecastPeriods, // "YYYY-MM-DD" string (Option A)
        // If backend needs integer, use this instead:
        // forecast_periods: dayjs(forecastPeriods).diff(dayjs(trainEndDate), "month"),
      },
    };

    try {
      setLoading(true);
      // Use HCV-specific configuration API when TA is HCV
      if (therapyArea === "HCV") {
        await saveConfigurationsHCV(payload);
      } else {
        await saveConfigurations(payload);
      }
      showSnackbar("Configurations saved successfully", "success");
      // Signal ModelInput to auto-apply the saved config on next open
      try { localStorage.setItem("hcvConfigSaved", String(Date.now())); } catch (e) { /* ignore */ }
    } catch (error) {
      console.error("Save configuration failed:", error);
      const errorMessage =
        error?.response?.data?.detail || "Failed to save configuration";
      showSnackbar(errorMessage, "error");
    } finally {
      setLoading(false);
    }
  };

  // ── STYLES ───────────────────────────────────────────────────────────────
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

  // ── RENDER ───────────────────────────────────────────────────────────────
  return (
    <Box sx={{ p: 3 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Typography
          sx={{ fontSize: "24px", fontWeight: 700, color: "#0A2342" }}
        >
          Global Configurations
        </Typography>
      </Box>

      <Typography sx={{ fontSize: "16px", color: "#5B708B", mt: 1, mb: 3 }}>
        Define your model parameters and therapeutic scope.
      </Typography>

      {/* ── Therapeutic Area ── */}
      <Paper
        sx={{
          p: 3,
          borderRadius: "16px",
          boxShadow: "none",
          border: "1px solid #D8DEE8",
        }}
      >
        <Typography
          sx={{ fontSize: "16px", fontWeight: 600, color: "#64748b", mb: 1 }}
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
      </Paper>

      {/* ── Time Horizon & Granularity ── */}
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
          sx={{ fontSize: "18px", fontWeight: 700, color: "#0A2342", mb: 2 }}
        >
          Time Horizon & Granularity
        </Typography>

        {/* Row 1 — Payer + Product */}
        <Box sx={{ display: "flex", gap: 3, mb: 3 }}>
          <Box sx={{ flex: 1 }}>
            <Typography
              sx={{
                mb: 1,
                fontSize: "16px",
                fontWeight: 600,
                color: "#64748b",
              }}
            >
              PAYER
            </Typography>
            <FormControl fullWidth size="small" error={!!errors.payer}>
              <Select
                multiple
                value={payer}
                onChange={(e) => {
                  const value = e.target.value;
                  const opts = ["commercial", "medicare", "medicaid"];
                  if (value.includes("SELECT_ALL")) {
                    if (payer.length === opts.length) setPayer([]);
                    else setPayer(opts);
                  } else {
                    setPayer(value);
                  }
                }}
                sx={inputStyle}
                displayEmpty
                renderValue={(selected) =>
                  selected.length === 0
                    ? "Select Payer"
                    : selected
                        .map((v) =>
                          v === "commercial"
                            ? "Commercial"
                            : v === "medicare"
                              ? "Medicare"
                              : "Medicaid",
                        )
                        .join(", ")
                }
              >
                <MenuItem value="SELECT_ALL">
                  <Checkbox
                    checked={payer.length === 3 && payer.length > 0}
                    indeterminate={payer.length > 0 && payer.length < 3}
                  />
                  <ListItemText primary="Select All" />
                </MenuItem>

                <MenuItem value="commercial"> <Checkbox checked={payer.includes("commercial")} /> <ListItemText primary="Commercial" /> </MenuItem>
                <MenuItem value="medicare"> <Checkbox checked={payer.includes("medicare")} /> <ListItemText primary="Medicare" /> </MenuItem>
                <MenuItem value="medicaid"> <Checkbox checked={payer.includes("medicaid")} /> <ListItemText primary="Medicaid" /> </MenuItem>
              </Select>
              <FormHelperText>{errors.payer}</FormHelperText>
            </FormControl>
          </Box>

          <Box sx={{ flex: 1 }}>
            <Typography
              sx={{
                mb: 1,
                fontSize: "16px",
                fontWeight: 600,
                color: "#64748b",
              }}
            >
              PRODUCT
            </Typography>
            <FormControl fullWidth size="small" error={!!errors.product}>
              <Select
                multiple
                value={product}
                onChange={(e) => {
                  const value = e.target.value;
                  const opts = ["GILD", "ASGA", "others"];
                  if (value.includes("SELECT_ALL")) {
                    if (product.length === opts.length) setProduct([]);
                    else setProduct(opts);
                  } else {
                    setProduct(value);
                  }
                }}
                sx={inputStyle}
                displayEmpty
                renderValue={(selected) =>
                  selected.length === 0 ? "Select Product" : selected.join(", ")
                }
              >
                <MenuItem value="SELECT_ALL">
                  <Checkbox
                    checked={product.length === 3 && product.length > 0}
                    indeterminate={product.length > 0 && product.length < 3}
                  />
                  <ListItemText primary="Select All" />
                </MenuItem>

                <MenuItem value="GILD"> <Checkbox checked={product.includes("GILD")} /> <ListItemText primary="GILD" /> </MenuItem>
                <MenuItem value="ASGA"> <Checkbox checked={product.includes("ASGA")} /> <ListItemText primary="ASGA" /> </MenuItem>
                <MenuItem value="others"> <Checkbox checked={product.includes("others")} /> <ListItemText primary="Others" /> </MenuItem>
              </Select>
              <FormHelperText>{errors.product}</FormHelperText>
            </FormControl>
          </Box>
        </Box>

        {/* Row 2 — Train Start + Train End */}
        <Box sx={{ display: "flex", gap: 3, mb: 3, flexWrap: "wrap" }}>
          <Box sx={{ flex: 1, minWidth: "320px" }}>
            <Typography
              sx={{
                mb: 1,
                fontSize: "16px",
                fontWeight: 600,
                color: "#64748b",
              }}
            >
              TRAIN START DATE
            </Typography>
            <LocalizationProvider
              dateAdapter={AdapterDayjs}
              localeText={globalConfigDateLocaleText}
            >
              <FormControl
                fullWidth
                size="small"
                error={!!errors.trainStartDate}
              >
                <Select
                  value={trainStartDate}
                  onChange={(e) => {
                    setTrainStartDate(e.target.value);
                    if (
                      trainEndDate &&
                      !dayjs(trainEndDate).isAfter(e.target.value)
                    ) {
                      setTrainEndDate("");
                    }
                  }}
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
            <Typography
              sx={{
                mb: 1,
                fontSize: "16px",
                fontWeight: 600,
                color: "#64748b",
              }}
            >
              TRAIN END DATE
            </Typography>
            <LocalizationProvider
              dateAdapter={AdapterDayjs}
              localeText={globalConfigDateLocaleText}
            >
              <FormControl fullWidth size="small" error={!!errors.trainEndDate}>
                <Select
                  value={trainEndDate}
                  onChange={(e) => setTrainEndDate(e.target.value)}
                  sx={inputStyle}
                  displayEmpty
                  disabled={!trainStartDate}
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
                    .filter((month) => dayjs(month).isAfter(trainStartDate))
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

        {/* Row 3 — Model Granularity + Forecast End Date */}
        <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
          <Box sx={{ flex: 1, minWidth: "320px" }}>
            <Typography
              sx={{
                mb: 1,
                fontSize: "16px",
                fontWeight: 600,
                color: "#64748b",
              }}
            >
              MODEL GRANULARITY
            </Typography>
            <FormControl
              fullWidth
              size="small"
              error={!!errors.modelGranularity}
            >
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
                  trainEndDate ? dayjs(trainEndDate).add(1, "month") : undefined
                }
                onChange={(newValue) =>
                  setForecastPeriods(
                    newValue
                      ? newValue.startOf("month").format("YYYY-MM-DD")
                      : "",
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

      <AverageVialsModal
        open={openModal}
        onClose={() => setOpenModal(false)}
        therapyArea={therapyArea}
      />
    </Box>
  );
}
