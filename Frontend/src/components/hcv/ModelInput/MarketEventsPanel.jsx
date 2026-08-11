import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Typography,
  Button,
  Menu,
  MenuItem,
  IconButton,
  TextField,
  FormControl,
  Select,
  OutlinedInput,
  Checkbox,
  ListItemText,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Chip,
  Collapse,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import EditIcon from "@mui/icons-material/EditOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import dayjs from "dayjs";

const DATE_INPUT_FORMATS = ["MMM-YY", "YYYY-MM", "YYYY-MM-DD", "YYYY-MM-DDTHH:mm:ssZ"];
const formatDateLabel = (s) => {
  if (!s) return "";
  const strict = dayjs(s, DATE_INPUT_FORMATS, true);
  const parsed = strict.isValid() ? strict : dayjs(s);
  return parsed.isValid() ? parsed.format("MMM-YY") : s;
};

// Same curve options exposed by the real Impact Curve Configuration (Market Events).
const CURVE_TYPES = ["Linear", "Exponential", "Logarithmic", "S-Curve"];

// PaymentType_Payer_Product event's "Payer" field is its own fixed list —
// CVS / Non CVS — not the payment-type list used by other event types.
const CVS_PAYER_OPTIONS = ["CVS", "Non CVS"];

const SELECT_ALL = "__SELECT_ALL__";

// "Payer" event's own field is actually the Payment Type dimension
// (Cash/Commercial/Medicaid/Medicare) — the internal eventType value stays
// "Payer" (matches the backend's payer_event enum), only the text shown to
// the user changes.
const eventTypeLabel = (et) =>
  et === "PaymentType_Payer_Product" ? "PT_Payer_Prod" : et === "Payer" ? "Payment Type" : et;

// Mirrors Market Events' Impact Curve Configuration row fields exactly —
// event_name, products, markets (payers), impacted_items, start_date,
// peak_percent, months, curve_type, factor.
const emptyForm = {
  name: "",
  paymentTypes: [],
  products: [],
  payers: [],
  impactedItems: [],
  sourcePercentages: {},
  startDate: "",
  peakPercent: "",
  months: "",
  curveType: CURVE_TYPES[0],
  factor: "",
};

// Reusable panel shared by the Total Market Volume tab (compact list) and the
// Events Management tab (full table) so both stay backed by the same events state.
export default function MarketEventsPanel({
  variant = "compact",
  events = [],
  // Adds/updates a row locally AND immediately persists the full event
  // list to the backend (POST /api/liver-market-events/save) — there's no
  // separate batch-save step, every "Save Event" click hits the API.
  onSave,
  onDelete,
  productOptions = [],
  payerOptions = [],
  availableDates = [],
  // "Run Calculation" button (compact variant only, next to the Market
  // Events dropdown) — triggers POST /api/liver-market-events/run-calculation.
  onRunCalculation,
  runningCalculation = false,
}) {
  const [addMenuAnchor, setAddMenuAnchor] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [eventType, setEventType] = useState("Product");
  const [form, setForm] = useState(emptyForm);
  const [saveError, setSaveError] = useState("");

  // ── Impact Dialog state (mirrors MarketEvent.jsx) ───────────────────
  const [openImpactDialog, setOpenImpactDialog] = useState(false);
  const [impactValues, setImpactValues] = useState({});

  // Which events (created via the Events Management tab) are shown in the
  // compact panel — auto-includes new events, drops ones that get deleted.
  const [selectedEventIds, setSelectedEventIds] = useState(() => events.map((e) => e.id));
  const knownEventIdsRef = useRef(new Set(events.map((e) => e.id)));
  useEffect(() => {
    const currentIds = new Set(events.map((e) => e.id));
    const newIds = events.map((e) => e.id).filter((id) => !knownEventIdsRef.current.has(id));
    knownEventIdsRef.current = currentIds;
    if (newIds.length) {
      setSelectedEventIds((prev) => [...prev, ...newIds]);
    } else {
      setSelectedEventIds((prev) => prev.filter((id) => currentIds.has(id)));
    }
  }, [events]);

  // Only future months make sense as a launch date for a new event.
  const futureDates = useMemo(() => {
    const idx = availableDates.indexOf(dayjs().format("MMM-YY"));
    return idx === -1 ? availableDates : availableDates.slice(idx);
  }, [availableDates]);

  const toggleMultiSelect = (field, options) => (e) => {
    const value = e.target.value;
    if (value.includes(SELECT_ALL)) {
      setForm((f) => ({
        ...f,
        [field]: f[field].length === options.length ? [] : options,
      }));
      return;
    }
    setForm((f) => ({ ...f, [field]: value }));
  };

  const openAddForm = (type) => {
    setEventType(type);
    setEditingId(null);
    setSaveError("");
    setForm({ ...emptyForm, startDate: futureDates[0] || availableDates[0] || "" });
    setAddMenuAnchor(null);
    setFormOpen(true);
  };

  const openEditForm = (evt) => {
    setEventType(evt.eventType);
    setEditingId(evt.id);
    setSaveError("");
    setForm({
      name: evt.name,
      paymentTypes: [...(evt.paymentTypes || [])],
      products: [...evt.products],
      payers: [...evt.payers],
      impactedItems: [...evt.impactedItems],
      sourcePercentages: { ...(evt.sourcePercentages || {}) },
      startDate: evt.startDate,
      peakPercent: evt.peakPercent,
      months: evt.months,
      curveType: evt.curveType,
      factor: evt.factor,
    });
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingId(null);
    setSaveError("");
  };

  const handleSave = () => {
    if (!form.name.trim() || !form.startDate) {
      setSaveError("Please fill in event name and start date.");
      return;
    }

    // Derive impacted items from source percentages (same as MarketEvent.jsx)
    const impactedItems = Object.keys(form.sourcePercentages).filter(
      (key) => !form.products.includes(key) && !form.payers.includes(key),
    );

    onSave?.({
      id: editingId ?? Date.now(),
      eventType,
      name: form.name.trim(),
      paymentTypes: [...form.paymentTypes],
      products: [...form.products],
      payers: [...form.payers],
      impactedItems,
      sourcePercentages: { ...form.sourcePercentages },
      startDate: form.startDate,
      peakPercent: Number(form.peakPercent) || 0,
      months: Number(form.months) || 0,
      curveType: form.curveType,
      factor: form.curveType === "Linear" ? 0 : Number(form.factor) || 0,
    });
    closeForm();
  };

  const addEventButton = (
    <>
      <Button
        size="small"
        variant="contained"
        startIcon={<AddIcon />}
        onClick={(e) => setAddMenuAnchor(e.currentTarget)}
        sx={{ textTransform: "none", borderRadius: "6px", backgroundColor: "#4F46E5", fontSize: "12px" }}
      >
        Add Event
      </Button>
      <Menu anchorEl={addMenuAnchor} open={!!addMenuAnchor} onClose={() => setAddMenuAnchor(null)}>
        <MenuItem onClick={() => openAddForm("Product")}>Product event</MenuItem>
        <MenuItem onClick={() => openAddForm("Payer")}>Payment type event</MenuItem>
        <MenuItem onClick={() => openAddForm("PaymentType_Payer_Product")}>Payment type_Payer_Product event</MenuItem>
      </Menu>
    </>
  );

  const sourcesLabel = (items) => (items && items.length ? items.join(", ") : "N/A");

  const renderMultiSelectSummary = (selected, placeholder) => {
    if (!selected.length) return placeholder;
    return selected.join(", ");
  };

  // Shared multi-select w/ "Select All" — matches Market Events' Impact
  // Curve Configuration Products/Payers/Impacted selects.
  // ── Compact input styles — sized to fit all fields on one row ────────
  const compactInputStyle = {
    "& .MuiOutlinedInput-root": {
      height: "32px",
      borderRadius: "6px",
      backgroundColor: "#fff",
      fontSize: "13px",
    },
    // Without this, the input's default (much taller) padding doesn't fit
    // inside the 32px height above, so the field renders an internal
    // scrollbar instead of just vertically centering the text — same fix
    // already applied to the Impact dialog's number fields below.
    "& input": { padding: "6px 12px" },
  };
  const compactSelectStyle = {
    "& .MuiOutlinedInput-root": {
      height: "32px",
      borderRadius: "6px",
      backgroundColor: "#fff",
      fontSize: "13px",
      paddingRight: "32px",
    },
    "& .MuiSelect-select": {
      display: "flex",
      alignItems: "center",
      padding: "6px 12px",
      minHeight: "unset !important",
    },
    "& .MuiSelect-icon": {
      color: "#64748b",
      right: 8,
      fontSize: 22,
    },
  };
  const labelStyle = { mb: 0.5, fontSize: "11px", fontWeight: 700, color: "#64748b" };

  const renderMultiSelect = (field, label, options, disabled = false) => (
    <Box sx={{ minWidth: 0 }}>
      <Typography sx={labelStyle}>{label.toUpperCase()}</Typography>
      <FormControl size="small" fullWidth sx={compactSelectStyle} disabled={disabled}>
        <Select
          multiple
          displayEmpty
          disabled={disabled}
          value={form[field]}
          onChange={toggleMultiSelect(field, options)}
          input={<OutlinedInput />}
          renderValue={(selected) => renderMultiSelectSummary(selected, "Select")}
        >
          <MenuItem value={SELECT_ALL}>
            <Checkbox
              size="small"
              checked={form[field].length === options.length && options.length > 0}
              indeterminate={form[field].length > 0 && form[field].length < options.length}
            />
            <ListItemText primary="Select All" />
          </MenuItem>
          {options.map((opt) => (
            <MenuItem key={opt} value={opt}>
              <Checkbox size="small" checked={form[field].includes(opt)} />
              <ListItemText primary={opt} />
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );

  // Single-choice version of the field above, for Product event's Products
  // dropdown (only that one, per request — Payer and PaymentType_Payer_Product
  // events still allow multiple products). Keeps form[field] as a
  // single-element array under the hood so the rest of the component
  // (impact-dialog exclusion, save payload, table display) doesn't need to
  // special-case this field's shape — it just always contains 0 or 1 items.
  const renderSingleSelect = (field, label, options, disabled = false) => (
    <Box sx={{ minWidth: 0 }}>
      <Typography sx={labelStyle}>{label.toUpperCase()}</Typography>
      <FormControl size="small" fullWidth sx={compactSelectStyle} disabled={disabled}>
        <Select
          displayEmpty
          disabled={disabled}
          value={form[field][0] || ""}
          onChange={(e) => {
            const val = e.target.value;
            setForm((f) => ({ ...f, [field]: val ? [val] : [] }));
          }}
          input={<OutlinedInput />}
          renderValue={(selected) => selected || "Select"}
        >
          {options.map((opt) => (
            <MenuItem key={opt} value={opt}>
              {opt}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );

  // ── Impact Dialog handlers (mirrors MarketEvent.jsx) ────────────────
  // For Payer event (displayed as "Payment Type" — see eventTypeLabel) →
  // impacted = payment types not selected as source payment types.
  // For Product event → impacted = products not selected as source products.
  // For PaymentType_Payer_Product → impacted = products not selected as source products.
  const isPayerEvent = eventType === "Payer";
  const isPPPEvent = eventType === "PaymentType_Payer_Product";
  const impactOptions = isPayerEvent ? payerOptions : productOptions;
  const selectedSourceItems = isPayerEvent ? form.payers : form.products;

  // PaymentType_Payer_Product: the Payer (CVS / Non CVS) field only doesn't
  // apply when "Cash" is the ONLY selected Payment Type — Cash has no payer
  // split, but if Cash is selected alongside Commercial/Medicaid/Medicare
  // (which do have one), the field is still relevant and must stay enabled.
  // Clear any previously-selected payer value when it becomes disabled, so
  // a disabled field doesn't silently keep a stale selection.
  const isCashPaymentTypeSelected =
    isPPPEvent && form.paymentTypes.length === 1 && form.paymentTypes[0] === "Cash";
  useEffect(() => {
    if (isCashPaymentTypeSelected && form.payers.length) {
      setForm((f) => ({ ...f, payers: [] }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCashPaymentTypeSelected]);

  const handleOpenImpactDialog = () => {
    const initial = {};
    impactOptions.forEach((opt) => {
      initial[opt] = Number(form.sourcePercentages?.[opt] || 0);
    });
    setImpactValues(initial);
    setOpenImpactDialog(true);
  };

  const handleSaveImpactDialog = () => {
    const impactedItems = impactOptions.filter(
      (opt) => !selectedSourceItems.includes(opt),
    );
    const sanitizedPercentages = impactedItems.reduce((acc, opt) => {
      acc[opt] = Number(impactValues[opt] || 0);
      return acc;
    }, {});
    setForm((f) => ({
      ...f,
      impactedItems: impactedItems,
      sourcePercentages: sanitizedPercentages,
    }));
    setOpenImpactDialog(false);
  };

  const handleCloseImpactDialog = () => {
    setOpenImpactDialog(false);
  };

  // Derived values for the impact dialog
  const impactedOptionValues = impactOptions.filter(
    (opt) => !selectedSourceItems.includes(opt),
  );
  const impactTotal = impactedOptionValues.reduce(
    (sum, opt) => sum + Number(impactValues[opt] || 0),
    0,
  );
  const isImpactValid =
    impactedOptionValues.length === 0 || Math.abs(impactTotal - 100) < 0.0001;

  const impactDialog = (
    <Dialog
      open={openImpactDialog}
      onClose={handleCloseImpactDialog}
      PaperProps={{
        sx: {
          width: "320px",
          maxWidth: "90vw",
          borderRadius: "12px",
        },
      }}
    >
      <DialogTitle
        sx={{
          fontWeight: 700,
          fontSize: "16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          pr: 1,
        }}
      >
        {isPayerEvent ? "Impacted Payment Types (%)" : "Source of Business (%)"}
        <IconButton size="small" onClick={handleCloseImpactDialog}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 1, display: "flex", flexDirection: "column", gap: 2 }}>
          {impactOptions.map((opt) => {
            const disabled = selectedSourceItems.includes(opt);
            return (
              <Box
                key={opt}
                sx={{ display: "flex", alignItems: "center", gap: 7 }}
              >
                <Typography
                  sx={{
                    width: "120px",
                    flexShrink: 0,
                    fontSize: "14px",
                    color: disabled ? "#94A3B8" : "#334155",
                  }}
                >
                  {opt}
                </Typography>
                <TextField
                  type="number"
                  size="small"
                  disabled={disabled}
                  value={impactValues[opt] ?? 0}
                  onChange={(e) =>
                    setImpactValues((prev) => ({
                      ...prev,
                      [opt]: Number(e.target.value || 0),
                    }))
                  }
                  sx={{
                    width: "65px",
                    "& .MuiOutlinedInput-root": {
                      height: "30px",
                      fontSize: "13px",
                      backgroundColor: disabled ? "#E2E8F0" : "#fff",
                    },
                    "& input": { padding: "6px 8px" },
                  }}
                />
              </Box>
            );
          })}

          {!isImpactValid && (
            <Typography sx={{ fontSize: "12px", color: "#EF4444", mt: 1 }}>
              Total must equal 100%.
            </Typography>
          )}
        </Box>

        <DialogActions sx={{ p: 0, pt: 3 }}>
          <Button
            fullWidth
            variant="contained"
            disabled={!isImpactValid}
            onClick={handleSaveImpactDialog}
            sx={{
              textTransform: "none",
              borderRadius: "8px",
              height: "42px",
              backgroundColor: "#4F46E5",
            }}
          >
            Done
          </Button>
        </DialogActions>
      </DialogContent>
    </Dialog>
  );

  const formPanel = (
    <Collapse in={formOpen} unmountOnExit>
      <Box
        sx={{
          border: "1px solid #D8DEE8",
          borderRadius: "8px",
          p: 2,
          mb: 2,
          backgroundColor: "#fff",
        }}
      >
        {/* ── Header row ── */}
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1.5 }}>
          <Typography sx={{ fontWeight: 700, fontSize: "14px", color: "#0f172a" }}>
            {editingId ? `Edit ${eventTypeLabel(eventType)} Event` : `Add ${eventTypeLabel(eventType)} Event`}
          </Typography>
          <IconButton size="small" onClick={closeForm}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>

        {/* ── All fields on one row — CSS grid, horizontal scroll if needed ── */}
        <Box sx={{ overflowX: "auto" }}>
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: isPPPEvent
                ? "1fr 0.8fr 0.8fr 0.8fr auto 0.7fr 0.5fr 0.5fr 0.7fr 0.55fr"
                : "1fr 0.9fr 0.9fr auto 0.75fr 0.55fr 0.55fr 0.75fr 0.6fr",
              gap: 1.5,
              alignItems: "end",
              minWidth: isPPPEvent ? 1400 : 1200,
            }}
          >
            {/* Event Name */}
            <Box>
              <Typography sx={labelStyle}>EVENT NAME</Typography>
              <TextField
                placeholder={
                  isPPPEvent
                    ? "PT_Payer_Product Event"
                    : `${eventTypeLabel(eventType)} Event`
                }
                size="small"
                fullWidth
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                sx={compactInputStyle}
              />
            </Box>

            {/* Source selects — order depends on event type. The SECOND
                field for every event type is single-select (only the
                first/context field allows multiple). */}
            {isPPPEvent ? (
              <>
                {renderMultiSelect("paymentTypes", "Payment Type", payerOptions)}
                {renderSingleSelect("payers", "Payer", CVS_PAYER_OPTIONS, isCashPaymentTypeSelected)}
                {renderSingleSelect("products", "Products", productOptions)}
              </>
            ) : isPayerEvent ? (
              <>
                {renderMultiSelect("products", "Products", productOptions)}
                {renderSingleSelect("payers", "Payment Type", payerOptions)}
              </>
            ) : (
              <>
                {renderMultiSelect("payers", "Payment Type", payerOptions)}
                {renderSingleSelect("products", "Products", productOptions)}
              </>
            )}

            {/* Impacted — "Edit Source" button */}
            <Box>
              <Typography sx={labelStyle}>
                {isPayerEvent ? "IMPACTED PAYMENT TYPES" : "SOURCE OF BUSINESS"}
              </Typography>
              <Button
                variant="outlined"
                onClick={handleOpenImpactDialog}
                sx={{
                  textTransform: "none",
                  borderRadius: "6px",
                  height: "32px",
                  fontSize: "12px",
                  minWidth: "90px",
                  borderColor: "#D8DEE8",
                  color: "#334155",
                }}
              >
                Edit Source
              </Button>
            </Box>

            {/* Start Date */}
            <Box>
              <Typography sx={labelStyle}>START DATE</Typography>
              <FormControl size="small" fullWidth sx={compactSelectStyle}>
                <Select
                  value={form.startDate}
                  onChange={(e) => setForm((f) => ({ ...f, startDate: e.target.value }))}
                  displayEmpty
                >
                  {futureDates.map((d) => (
                    <MenuItem key={d} value={d}>
                      {formatDateLabel(d)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>

            {/* Peak % */}
            <Box>
              <Typography sx={labelStyle}>PEAK %</Typography>
              <TextField
                placeholder="0"
                type="number"
                size="small"
                fullWidth
                value={form.peakPercent}
                onChange={(e) => setForm((f) => ({ ...f, peakPercent: e.target.value }))}
                sx={compactInputStyle}
              />
            </Box>

            {/* Months */}
            <Box>
              <Typography sx={labelStyle}>MONTHS</Typography>
              <TextField
                placeholder="0"
                type="number"
                size="small"
                fullWidth
                value={form.months}
                onChange={(e) => setForm((f) => ({ ...f, months: e.target.value }))}
                sx={compactInputStyle}
              />
            </Box>

            {/* Curve */}
            <Box>
              <Typography sx={labelStyle}>CURVE</Typography>
              <FormControl size="small" fullWidth sx={compactSelectStyle}>
                <Select
                  value={form.curveType}
                  onChange={(e) => setForm((f) => ({ ...f, curveType: e.target.value }))}
                >
                  {CURVE_TYPES.map((c) => (
                    <MenuItem key={c} value={c}>
                      {c}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>

            {/* Factor */}
            <Box>
              <Typography sx={labelStyle}>FACTOR</Typography>
              <TextField
                placeholder="0"
                type="number"
                size="small"
                fullWidth
                disabled={form.curveType === "Linear"}
                value={form.factor}
                onChange={(e) => setForm((f) => ({ ...f, factor: e.target.value }))}
                sx={{
                  ...compactInputStyle,
                  "& .MuiOutlinedInput-root": {
                    ...compactInputStyle["& .MuiOutlinedInput-root"],
                    backgroundColor: form.curveType === "Linear" ? "#F3F4F6" : "#fff",
                  },
                }}
              />
            </Box>
          </Box>
        </Box>

        {/* ── Error + Action buttons ── */}
        {saveError && (
          <Typography sx={{ fontSize: "12px", color: "#ef4444", mt: 1.5 }}>{saveError}</Typography>
        )}

        <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1, mt: 2, pt: 1.5, borderTop: "1px solid #D8DEE8" }}>
          <Button
            variant="outlined"
            onClick={closeForm}
            sx={{ textTransform: "none", borderRadius: "8px", color: "#64748b", borderColor: "#D8DEE8", fontSize: "12px" }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            sx={{ textTransform: "none", borderRadius: "8px", backgroundColor: "#4F46E5", fontSize: "12px" }}
          >
            Save Event
          </Button>
        </Box>
      </Box>
    </Collapse>
  );

  if (variant === "table") {
    return (
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1.5 }}>
          <Typography sx={{ fontWeight: 700, fontSize: "16px" }}>Manage Market Events</Typography>
          {addEventButton}
        </Box>
        {formPanel}
        <Box sx={{ border: "1px solid #e2e8f0", borderRadius: "8px", overflow: "hidden" }}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ backgroundColor: "#f8fafc" }}>
                <TableCell>Type</TableCell>
                <TableCell>Event Name</TableCell>
                <TableCell>Payment Types</TableCell>
                <TableCell>Products</TableCell>
                <TableCell>Payment Type</TableCell>
                <TableCell>Impacted</TableCell>
                <TableCell>Start Date</TableCell>
                <TableCell>Peak %</TableCell>
                <TableCell>Months</TableCell>
                <TableCell>Curve</TableCell>
                <TableCell>Factor</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {events.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={12} sx={{ textAlign: "center", color: "#64748b", fontSize: "12px" }}>
                    No events created. Click "Add Event" to create one.
                  </TableCell>
                </TableRow>
              ) : (
                events.map((evt) => (
                  <TableRow key={evt.id}>
                    <TableCell>
                      <Chip
                        label={eventTypeLabel(evt.eventType)}
                        size="small"
                        sx={{ fontWeight: 700, fontSize: "10px" }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>{evt.name}</TableCell>
                    <TableCell>{sourcesLabel(evt.paymentTypes)}</TableCell>
                    <TableCell>{sourcesLabel(evt.products)}</TableCell>
                    <TableCell>{sourcesLabel(evt.payers)}</TableCell>
                    <TableCell>{sourcesLabel(evt.impactedItems)}</TableCell>
                    <TableCell>{formatDateLabel(evt.startDate)}</TableCell>
                    <TableCell>{evt.peakPercent}%</TableCell>
                    <TableCell>{evt.months} M</TableCell>
                    <TableCell>{evt.curveType}</TableCell>
                    <TableCell>{evt.curveType === "Linear" ? "—" : evt.factor}</TableCell>
                    <TableCell>
                      <IconButton size="small" onClick={() => openEditForm(evt)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton size="small" onClick={() => onDelete?.(evt.id)}>
                        <DeleteOutlineIcon fontSize="small" sx={{ color: "#ef4444" }} />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Box>
        {impactDialog}
      </Box>
    );
  }

  // variant === "compact" — Total Market Volume tab panel
  const selectedEvents = events.filter((evt) => selectedEventIds.includes(evt.id));
  return (
    <Box sx={{ mb: 3, p: 2, border: "1px solid #e2e8f0", borderRadius: "8px", backgroundColor: "white" }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1.5 }}>
        <Typography sx={{ fontWeight: 700, fontSize: "14px" }}>Market Events</Typography>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          {onRunCalculation && (
            <Button
              variant="contained"
              size="small"
              onClick={onRunCalculation}
              disabled={runningCalculation}
              sx={{
                textTransform: "none",
                fontSize: "12px",
                fontWeight: 700,
                borderRadius: "6px",
                backgroundColor: "#2563EB",
                boxShadow: "none",
                "&:hover": { backgroundColor: "#1D4ED8", boxShadow: "none" },
              }}
            >
              {runningCalculation ? "Running..." : "Run Calculation"}
            </Button>
          )}
          <FormControl size="small" sx={{ width: 240, minWidth: 240 }}>
            <Select
              multiple
              displayEmpty
              value={selectedEventIds}
              onChange={(e) => setSelectedEventIds(e.target.value)}
              input={<OutlinedInput />}
              sx={{
                fontSize: "12px",
                "& .MuiSelect-select": { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
              }}
              MenuProps={{ PaperProps: { sx: { maxHeight: 260 } } }}
              renderValue={(selected) => {
                if (!events.length) return "No events created";
                if (!selected.length) return "Select Events";
                if (selected.length === events.length) return "All Events";
                return `${selected.length} Selected`;
              }}
            >
              {events.length === 0 ? (
                <MenuItem disabled>No events created yet</MenuItem>
              ) : (
                events.map((evt) => (
                  <MenuItem key={evt.id} value={evt.id}>
                    <Checkbox size="small" checked={selectedEventIds.includes(evt.id)} />
                    <ListItemText primary={`${evt.name} (${eventTypeLabel(evt.eventType)})`} />
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>
        </Box>
      </Box>
      {selectedEvents.length === 0 ? (
        <Typography sx={{ fontSize: "11px", color: "#64748b" }}>
          {events.length === 0
            ? "No market events created yet. Add one from the Events Management tab."
            : "No events selected. Use the dropdown above to show market events here."}
        </Typography>
      ) : (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {selectedEvents.map((evt) => (
            <Box
              key={evt.id}
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                backgroundColor: "#f8fafc",
                border: "1px solid #e2e8f0",
                borderRadius: "6px",
                px: 1.5,
                py: 1,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                <Chip
                  label={eventTypeLabel(evt.eventType)}
                  size="small"
                  sx={{ fontWeight: 700, fontSize: "10px" }}
                />
                <Typography sx={{ fontSize: "12px", fontWeight: 700 }}>{evt.name}</Typography>
                <Typography sx={{ fontSize: "11px", color: "#64748b" }}>
                  {evt.eventType === "PaymentType_Payer_Product" && `PT: ${sourcesLabel(evt.paymentTypes)} | `}
                  Products: {sourcesLabel(evt.products)} | Payment Type: {sourcesLabel(evt.payers)} | Starts:{" "}
                  {formatDateLabel(evt.startDate)} | Peak: {evt.peakPercent}% over {evt.months}M ({evt.curveType})
                </Typography>
              </Box>
              <IconButton
                size="small"
                onClick={() => setSelectedEventIds((prev) => prev.filter((id) => id !== evt.id))}
                title="Hide from this panel"
              >
                <CloseIcon fontSize="small" sx={{ color: "#ef4444" }} />
              </IconButton>
            </Box>
          ))}
        </Box>
      )}
      {formPanel}
      {impactDialog}
    </Box>
  );
}