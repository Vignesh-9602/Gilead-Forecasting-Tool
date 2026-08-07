import React, { useState, useEffect, useContext, useRef, useMemo } from "react";
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
import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs from "dayjs";
import { useSnackbarStore } from "../../../stores";
import {
  saveConfigurations,
  getConfigurationByTherapyArea,
  saveConfigurationsHCV,
  getConfigurationByTherapyAreaHCV,
} from "../../../services/apiService";
import { GlobalContext } from "../../../context/Provider";
import AverageVialsModal from "../../headerTabs/AvgVialsDialog";

const DATE_LOCALE_TEXT = {
  fieldMonthPlaceholder: () => "MM",
  fieldYearPlaceholder: () => "YYYY",
};

const INPUT_SX = {
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

const COMPACT_MENU_PROPS = {
  PaperProps: {
    sx: {
      maxHeight: 250,
      width: 120,
      "& .MuiMenuItem-root": { minHeight: 32, fontSize: "14px", py: 0.5 },
    },
  },
};

const LABEL_SX = { mb: 1, fontSize: "16px", fontWeight: 600, color: "#64748b" };

const cleanArray = (arr) => (arr || []).filter((v) => v !== "" && v != null);

const isHCV = (ta) => ta === "HCV";

const getConfig = (ta) =>
  isHCV(ta) ? getConfigurationByTherapyAreaHCV(ta) : getConfigurationByTherapyArea(ta);

const saveConfig = (ta, payload) =>
  isHCV(ta) ? saveConfigurationsHCV(payload) : saveConfigurations(payload);

// ─── Reusable multi-select with "Select All" ────────────────────────────────
function MultiSelect({ value, onChange, options, placeholder, error, helperText, disabled = false }) {
  const handleChange = (e) => {
    const selected = e.target.value;
    if (selected.includes("SELECT_ALL")) {
      onChange(value.length === options.length ? [] : [...options]);
    } else {
      onChange(selected);
    }
  };

  return (
    <FormControl fullWidth size="small" error={!!error}>
      <Select
        multiple
        value={value}
        onChange={handleChange}
        sx={INPUT_SX}
        displayEmpty
        disabled={disabled}
        renderValue={(sel) => (sel.length === 0 ? placeholder : sel.join(", "))}
      >
        <MenuItem value="SELECT_ALL">
          <Checkbox
            checked={value.length === options.length && value.length > 0}
            indeterminate={value.length > 0 && value.length < options.length}
          />
          <ListItemText primary="Select All" />
        </MenuItem>
        {options.map((opt) => (
          <MenuItem key={opt} value={opt}>
            <Checkbox checked={value.includes(opt)} />
            <ListItemText primary={opt} />
          </MenuItem>
        ))}
      </Select>
      {helperText && <FormHelperText>{helperText}</FormHelperText>}
    </FormControl>
  );
}

// ─── Date dropdown (month selector from available list) ─────────────────────
function MonthSelect({ value, onChange, options, placeholder, error, helperText, disabled = false }) {
  return (
    <LocalizationProvider dateAdapter={AdapterDayjs} localeText={DATE_LOCALE_TEXT}>
      <FormControl fullWidth size="small" error={!!error}>
        <Select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          sx={INPUT_SX}
          displayEmpty
          disabled={disabled}
          MenuProps={COMPACT_MENU_PROPS}
          renderValue={(sel) => (sel ? dayjs(sel).format("MMM YY") : placeholder)}
        >
          {options.map((month) => (
            <MenuItem key={month} value={month}>
              {dayjs(month).format("MMM YY")}
            </MenuItem>
          ))}
        </Select>
        {helperText && <FormHelperText>{helperText}</FormHelperText>}
      </FormControl>
    </LocalizationProvider>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────────
export default function GlobalConfiguration() {
  const [modelGranularity, setModelGranularity] = useState("");
  const [trainStartDate, setTrainStartDate] = useState("");
  const [trainEndDate, setTrainEndDate] = useState("");
  const [forecastPeriods, setForecastPeriods] = useState("");
  const [paymentType, setPaymentType] = useState([]);
  const [payer, setPayer] = useState([]);
  const [product, setProduct] = useState([]);
  const [errors, setErrors] = useState({});
  const [openModal, setOpenModal] = useState(false);

  const [availableTrainMonths, setAvailableTrainMonths] = useState([]);
  const [availablePaymentTypes, setAvailablePaymentTypes] = useState([]);
  const [availablePayers, setAvailablePayers] = useState({});
  const [availableBrands, setAvailableBrands] = useState([]);

  const [pageLoading, setPageLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const { showSnackbar } = useSnackbarStore();
  const { favState } = useContext(GlobalContext);
  const therapyArea = favState?.selectedTherapyArea;
  const fetchedTaRef = useRef(null);

  const derivedPayerOptions = useMemo(() => {
    if (!paymentType.length || !Object.keys(availablePayers).length) return [];
    const merged = new Set();
    paymentType.forEach((pt) => (availablePayers[pt] || []).forEach((p) => merged.add(p)));
    return [...merged];
  }, [paymentType, availablePayers]);

  useEffect(() => {
    if (!derivedPayerOptions.length) return setPayer([]);
    setPayer((prev) => prev.filter((p) => derivedPayerOptions.includes(p)));
  }, [derivedPayerOptions]);

  // Reset train end date if it's no longer after the start date
  const handleTrainStartChange = (value) => {
    setTrainStartDate(value);
    if (trainEndDate && !dayjs(trainEndDate).isAfter(value)) {
      setTrainEndDate("");
    }
  };

  const resetFields = () => {
    setTrainStartDate("");
    setTrainEndDate("");
    setModelGranularity("");
    setForecastPeriods("");
    setPaymentType([]);
    setPayer([]);
    setProduct([]);
  };

  // ─── Fetch ────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!therapyArea || fetchedTaRef.current === therapyArea) return;
    fetchedTaRef.current = therapyArea;
    fetchConfiguration(therapyArea);
  }, [therapyArea]);

  const fetchConfiguration = async (taName) => {
    try {
      setPageLoading(true);
      const { data } = await getConfig(taName);

      setAvailableTrainMonths(data?.available_train_months || []);
      setAvailablePaymentTypes(data?.available_payment_types || []);
      setAvailablePayers(data?.available_payers || {});
      setAvailableBrands(data?.available_brands || []);

      const config = data?.config;
      if (config) {
        setTrainStartDate(config.train_start_date || "");
        setTrainEndDate(config.train_end_date || "");
        setModelGranularity(config.model_granularity?.toLowerCase() || "");
        setForecastPeriods(config.forecast_periods || "");
        setPaymentType(cleanArray(config.payment_type));
        setPayer(cleanArray(config.payer));
        setProduct(cleanArray(config.brand));
      } else {
        resetFields();
      }
    } catch (err) {
      console.error("Failed to load configuration:", err);
      resetFields();
    } finally {
      setPageLoading(false);
    }
  };

  // ─── Save ─────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    const newErrors = {};
    if (!therapyArea) newErrors.therapyArea = "Therapeutic Area is required";
    if (!trainStartDate) newErrors.trainStartDate = "Train Start Date is required";
    if (!trainEndDate) newErrors.trainEndDate = "Train End Date is required";
    if (!modelGranularity) newErrors.modelGranularity = "Model Granularity is required";
    if (!forecastPeriods) newErrors.forecastPeriods = "Forecast End Date is required";

    setErrors(newErrors);
    if (Object.keys(newErrors).length > 0) {
      showSnackbar("Please fill all required fields", "error");
      return;
    }

    const payload = {
      config: {
        ta_name: therapyArea,
        payment_type: paymentType,
        payer,
        brand: product,
        train_start_date: trainStartDate,
        train_end_date: trainEndDate,
        model_granularity: modelGranularity,
        forecast_periods: forecastPeriods,
      },
    };

    try {
      setSaving(true);
      await saveConfig(therapyArea, payload);
      showSnackbar("Configurations saved successfully", "success");
      try { localStorage.setItem("hcvConfigSaved", String(Date.now())); } catch {}
    } catch (err) {
      const msg = err?.response?.data?.detail || "Failed to save configuration";
      showSnackbar(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  // ─── Derived helpers ──────────────────────────────────────────────────────
  const endDateOptions = availableTrainMonths.filter((m) => dayjs(m).isAfter(trainStartDate));

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <Box sx={{ p: 3 }}>
      <Typography sx={{ fontSize: "24px", fontWeight: 700, color: "#0A2342" }}>
        Global Configurations
      </Typography>
      <Typography sx={{ fontSize: "16px", color: "#5B708B", mt: 1, mb: 3 }}>
        Define your model parameters and therapeutic scope.
      </Typography>

      {/* Therapeutic Area */}
      <Paper sx={{ p: 3, borderRadius: "16px", boxShadow: "none", border: "1px solid #D8DEE8" }}>
        <Typography sx={{ ...LABEL_SX, mb: 1 }}>SELECTED THERAPEUTIC AREA</Typography>
        <Box
          sx={{
            height: 40, px: 2, display: "flex", alignItems: "center", gap: 1,
            border: "1px solid #D8DEE8", borderRadius: "8px", backgroundColor: "#d7dde6",
            width: "fit-content",
          }}
        >
          <Box sx={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: "#22c55e" }} />
          <Typography>{therapyArea}</Typography>
        </Box>
      </Paper>

      {/* Configuration Fields */}
      <Paper sx={{ p: 3, borderRadius: "16px", boxShadow: "none", border: "1px solid #D8DEE8", mt: 3 }}>
        <Typography sx={{ fontSize: "18px", fontWeight: 700, color: "#0A2342", mb: 2 }}>
          Time Horizon & Granularity
        </Typography>

        {/* Row 1 — Payment Type + Payer */}
        <Box sx={{ display: "flex", gap: 3, mb: 3 }}>
          <Box sx={{ flex: 1 }}>
            <Typography sx={LABEL_SX}>PAYMENT TYPE</Typography>
            <MultiSelect
              value={paymentType}
              onChange={setPaymentType}
              options={availablePaymentTypes}
              placeholder="Select Payment Type"
              error={errors.paymentType}
              helperText={errors.paymentType}
            />
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography sx={LABEL_SX}>PAYER</Typography>
            <MultiSelect
              value={payer}
              onChange={setPayer}
              options={derivedPayerOptions}
              placeholder="Select Payer"
              disabled={!derivedPayerOptions.length}
              error={errors.payer}
              helperText={errors.payer}
            />
          </Box>
        </Box>

        {/* Row 2 — Product + Train Start Date */}
        <Box sx={{ display: "flex", gap: 3, mb: 3 }}>
          <Box sx={{ flex: 1 }}>
            <Typography sx={LABEL_SX}>PRODUCT</Typography>
            <MultiSelect
              value={product}
              onChange={setProduct}
              options={availableBrands}
              placeholder="Select Product"
              error={errors.product}
              helperText={errors.product}
            />
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography sx={LABEL_SX}>TRAIN START DATE</Typography>
            <MonthSelect
              value={trainStartDate}
              onChange={handleTrainStartChange}
              options={availableTrainMonths}
              placeholder="Select Start Date"
              error={errors.trainStartDate}
              helperText={errors.trainStartDate}
            />
          </Box>
        </Box>

        {/* Row 3 — Train End Date + Model Granularity */}
        <Box sx={{ display: "flex", gap: 3, mb: 3 }}>
          <Box sx={{ flex: 1 }}>
            <Typography sx={LABEL_SX}>TRAIN END DATE</Typography>
            <MonthSelect
              value={trainEndDate}
              onChange={setTrainEndDate}
              options={endDateOptions}
              placeholder="Select End Date"
              disabled={!trainStartDate}
              error={errors.trainEndDate}
              helperText={errors.trainEndDate}
            />
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography sx={LABEL_SX}>MODEL GRANULARITY</Typography>
            <FormControl fullWidth size="small" error={!!errors.modelGranularity}>
              <Select
                value={modelGranularity}
                onChange={(e) => setModelGranularity(e.target.value)}
                sx={INPUT_SX}
                displayEmpty
              >
                <MenuItem value="" disabled>Select Model Granularity</MenuItem>
                <MenuItem value="monthly">Monthly</MenuItem>
                <MenuItem value="weekly">Weekly</MenuItem>
              </Select>
              <FormHelperText>{errors.modelGranularity}</FormHelperText>
            </FormControl>
          </Box>
        </Box>

        {/* Row 4 — Forecast End Date */}
        <Box sx={{ display: "flex", gap: 3 }}>
          <Box sx={{ flex: 1, maxWidth: "calc(50% - 12px)" }}>
            <Typography sx={LABEL_SX}>FORECAST END DATE</Typography>
            <LocalizationProvider dateAdapter={AdapterDayjs} localeText={DATE_LOCALE_TEXT}>
              <DatePicker
                views={["year", "month"]}
                value={forecastPeriods ? dayjs(forecastPeriods) : null}
                minDate={trainEndDate ? dayjs(trainEndDate).add(1, "month") : undefined}
                onChange={(val) =>
                  setForecastPeriods(val ? val.startOf("month").format("YYYY-MM-DD") : "")
                }
                format="MMM YY"
                slotProps={{
                  textField: {
                    fullWidth: true,
                    size: "small",
                    sx: INPUT_SX,
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
            disabled={saving || pageLoading}
            sx={{ backgroundColor: "#4F46E5", px: 2, py: 1, borderRadius: "10px", textTransform: "none" }}
          >
            {saving ? "Saving..." : "Save Configuration"}
          </Button>
        </Box>
      </Paper>

      <AverageVialsModal open={openModal} onClose={() => setOpenModal(false)} therapyArea={therapyArea} />
    </Box>
  );
}