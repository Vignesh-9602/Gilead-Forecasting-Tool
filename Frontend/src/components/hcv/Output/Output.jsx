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

// No hardcoded TA_NAME here — the actual selectedTherapyArea from context is
// used for both the API calls and the display label below, matching
// ModelInput.jsx's convention. A hardcoded constant would silently fetch
// HCV's data even while displaying a different therapy area's name.

/**
 * Output.jsx
 *
 * Starter component for the Output screen.
 * This contains the complete filter section only.
 * Remaining output widgets/charts/tables can be added below.
 */

export default function Output() {
    const { favState } = useContext(GlobalContext);

    const therapyArea = favState?.selectedTherapyArea || "HCV";

    // CVS/Non CVS is a fixed 2-value dimension, same as ModelInput.jsx's
    // hardcoded ["CVS", "Non CVS"] payer-filter options — it isn't fetched
    // from the filters endpoint.
    const SUB_PAYER_OPTIONS = ["CVS", "Non CVS"];

    // The apply-filter API response has no field for the CVS/Non CVS
    // selection at all, and the filters-list endpoint hasn't been
    // confirmed to echo it back reliably either — every attempt to
    // restore it from the API on load has come back empty. Persisting it
    // client-side instead guarantees a refresh doesn't lose it, regardless
    // of what the backend does or doesn't send back. Namespaced by therapy
    // area so switching areas doesn't leak one area's payer choice into
    // another's.
    const PAYER_STORAGE_KEY = `output_payer_filter_${therapyArea}`;
    const readStoredPayer = () => {
        try {
            const raw = window.localStorage.getItem(PAYER_STORAGE_KEY);
            const parsed = raw ? JSON.parse(raw) : [];
            return Array.isArray(parsed) ? parsed.filter((p) => SUB_PAYER_OPTIONS.includes(p)) : [];
        } catch (err) {
            return [];
        }
    };
    const writeStoredPayer = (value) => {
        try {
            window.localStorage.setItem(PAYER_STORAGE_KEY, JSON.stringify(value));
        } catch (err) {
            // Storage can be unavailable (private browsing, quota, etc.) —
            // the field just won't survive a refresh in that case, same as
            // before this change existed.
        }
    };

    const [availableScenarios, setAvailableScenarios] = useState([]);
    const [availableMonths, setAvailableMonths] = useState([]);
    const [availablePaymentTypes, setAvailablePaymentTypes] = useState([]);
    const [availableProducts, setAvailableProducts] = useState([]);

    const [selectedScenarios, setSelectedScenarios] = useState([]);
    const [selectedPaymentTypes, setSelectedPaymentTypes] = useState([]);
    const [selectedPayers, setSelectedPayers] = useState([]);
    const [selectedProducts, setSelectedProducts] = useState([]);

    // "Applied" mirrors — these, not the live dropdown state above, are
    // what get passed to OutputAnalysis. Only updated on a successful
    // fetch (initial load or Apply Filter), so editing a dropdown doesn't
    // change what the chart/table show until Apply Filter is actually
    // clicked. Same live-vs-applied split ModelInput.jsx uses (e.g.
    // productFilter vs appliedProductFilter).
    const [appliedScenarios, setAppliedScenarios] = useState([]);
    const [appliedPaymentTypes, setAppliedPaymentTypes] = useState([]);
    const [appliedPayers, setAppliedPayers] = useState([]);
    const [appliedProducts, setAppliedProducts] = useState([]);

    const [fromDate, setFromDate] = useState("");
    const [toDate, setToDate] = useState("");

    const [outputAnalysis, setOutputAnalysis] = useState(null);
    // API-provided {label, value} list for the metric dropdown — read
    // dynamically rather than hardcoded, matching ModelInput.jsx.
    const [metricFilters, setMetricFilters] = useState([]);
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
            const { data } = await getLiverOutputFilters(therapyArea);

            const availableScenariosList = data?.available_scenarios || [];
            const availablePaymentTypesList = data?.payers || [];
            const availableProductsList = data?.products || [];

            setAvailableScenarios(availableScenariosList);
            setAvailableMonths(data?.available_months || []);
            // NOTE: still reading the backend's existing "payers" field here —
            // it supplies the Cash/Commercial/Medicaid/Medicare list, now
            // relabeled "Payment Type" on this screen. If the backend also
            // renames this response field, update this line to match.
            setAvailablePaymentTypes(availablePaymentTypesList);
            setAvailableProducts(availableProductsList);

            const filter = data?.selected_filter || {};

            // The backend's selected_filter can go stale relative to its own
            // available_ lists (e.g. it still names a scenario that's since
            // been deleted). Drop anything that isn't actually a valid
            // option, otherwise it displays as "selected" in the dropdown
            // despite never being a real, choosable value.
            const validScenarioNames = (filter.scenario_names || []).filter((name) =>
                availableScenariosList.includes(name)
            );
            const validPaymentTypes = (filter.payers || []).filter((pt) =>
                availablePaymentTypesList.includes(pt)
            );
            const validProducts = (filter.products || []).filter((product) =>
                availableProductsList.includes(product)
            );

            // CVS/Non CVS is echoed back on filter.payer — same field
            // ModelInput.jsx reads for its equivalent dropdown, but
            // ModelInput's own two filter endpoints don't agree on its
            // shape: one echoes a bare string ("CVS"), the other an array
            // (["CVS"]). Normalize to an array first so either shape is
            // handled the same way, then validate against the two real
            // options before accepting it — the backend has been observed
            // echoing an unrelated payment-type value into this field too.
            const rawPayer = Array.isArray(filter.payer)
                ? filter.payer
                : filter.payer
                    ? [filter.payer]
                    : [];
            const apiPayer = rawPayer.filter((p) => SUB_PAYER_OPTIONS.includes(p));

            // The API's echoed payer has proven unreliable (comes back
            // empty even right after a refresh) — prefer whatever was last
            // persisted locally, and only fall back to the API's value on
            // a genuinely first-ever visit where nothing's been stored yet.
            const storedPayer = readStoredPayer();
            const validPayer = storedPayer.length ? storedPayer : apiPayer;

            setSelectedScenarios(validScenarioNames);
            setSelectedPaymentTypes(validPaymentTypes);
            setSelectedPayers(validPayer);
            setSelectedProducts(validProducts);
            setFromDate(filter.start_date || "");
            setToDate(filter.end_date || "");

            await fetchOutputAnalysis({
                scenario_names: validScenarioNames,
                payment_type: validPaymentTypes,
                payer: validPayer,
                products: validProducts,
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
        payment_type,
        payer,
        products,
        start_date,
        end_date,
    }) => {
        const payload = {
            ta: therapyArea,
            scenario_names,
            // The backend for this endpoint requires "payers" (confirmed
            // twice now via a pydantic "Field required" error) — it hasn't
            // been migrated to payment_type/payer. Keep sending both until
            // that migration happens.
            payers: payment_type,
            payment_type,
            payer,
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
            // metric_filters carries the API's own labels ("Payer Volume",
            // "Payer Share"), but ModelInput.jsx never shows those raw
            // backend labels to the user — it always displays "Market
            // Volume"/"Market Share" regardless of what the backend calls
            // the field internally (see its hardcoded defaultMetricOptions).
            // Keep the API's values (payer_volume/payer_share) since those
            // are the real keys used to look up data — only the label
            // shown in the dropdown is overridden, matching ModelInput's
            // display convention.
            const METRIC_LABEL_OVERRIDES = {
                payer_volume: "Market Volume",
                payer_share: "Market Share",
            };
            setMetricFilters(
                (data?.metric_filters || []).map((m) => ({
                    ...m,
                    label: METRIC_LABEL_OVERRIDES[m.value] || m.label,
                }))
            );
            // Only now — after a successful fetch — do the "applied"
            // mirrors move. Until this happens, live dropdown edits have
            // no effect on what OutputChart/OutputTable show.
            setAppliedScenarios(scenario_names);
            setAppliedPaymentTypes(payment_type);
            setAppliedPayers(payer);
            setAppliedProducts(products);
        } catch (err) {
            console.error("Failed to apply output filters", err);
        } finally {
            setIsApplyingFilters(false);
        }
    };

    const handleApplyFilter = () => {
        fetchOutputAnalysis({
            scenario_names: selectedScenarios,
            payment_type: selectedPaymentTypes,
            payer: selectedPayers,
            products: selectedProducts,
            start_date: fromDate,
            end_date: toDate,
        });
    };

    // Same rule as ModelInput.jsx's payerFilter === "Cash" check, extended
    // to multi-select: CVS/Non CVS only applies to non-Cash payment types.
    // Payer stays disabled if nothing is selected yet, or if every selected
    // payment type is Cash. As soon as any non-Cash payment type joins the
    // selection (with or without Cash also selected), payer becomes usable.
    const onlyCashSelected =
        selectedPaymentTypes.length > 0 &&
        selectedPaymentTypes.every((pt) => pt === "Cash");
    const isPayerFilterDisabled = selectedPaymentTypes.length === 0 || onlyCashSelected;

    const handlePaymentTypeChange = (val) => {
        setSelectedPaymentTypes(val);
        const willBeCashOnly = val.length > 0 && val.every((pt) => pt === "Cash");
        if (val.length === 0 || willBeCashOnly) {
            setSelectedPayers([]);
            writeStoredPayer([]);
        }
    };

    // Wraps setSelectedPayers so every user-driven change (checking/
    // unchecking CVS or Non CVS, Select All) is immediately persisted —
    // this is what actually survives a refresh now, not the API echo.
    const handlePayerChange = (val) => {
        setSelectedPayers(val);
        writeStoredPayer(val);
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
        setValue,
        disabled = false
    ) => (
        <Box>
            <Typography sx={labelStyle}>{label}</Typography>

            <FormControl sx={inputStyle} disabled={disabled}>
                <Select
                    multiple
                    value={value}
                    disabled={disabled}
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
                        "PAYMENT TYPE",
                        availablePaymentTypes,
                        selectedPaymentTypes,
                        handlePaymentTypeChange
                    )}

                    {renderMultiSelect(
                        "PAYER",
                        SUB_PAYER_OPTIONS,
                        selectedPayers,
                        handlePayerChange,
                        isPayerFilterDisabled
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
                        disabled={
                            isApplyingFilters ||
                            isLoadingFilters ||
                            !fromDate ||
                            !toDate ||
                            selectedPaymentTypes.length === 0 ||
                            (!onlyCashSelected && selectedPayers.length === 0)
                        }
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
                    metricFilters={metricFilters}
                    selectedScenarios={appliedScenarios}
                    selectedPaymentTypes={appliedPaymentTypes}
                    selectedPayers={appliedPayers}
                    selectedProducts={appliedProducts}
                />
            )}
        </Box>
    );
}