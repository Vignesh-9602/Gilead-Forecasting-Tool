import React, { useContext, useEffect, useState, useRef } from "react";

import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    Button,
    Tabs,
    Tab,
    TextField,
    Menu,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Checkbox,
    ListItemText,
    IconButton
} from "@mui/material";

import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

import dayjs from "dayjs";

import MoreVertIcon from "@mui/icons-material/MoreVert";
import CloseIcon from "@mui/icons-material/Close";

import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";

import { GlobalContext } from "../../../context/Provider";
import {
    getLiverMarketEventsFilters,
    applyLiverMarketEventsFilters,
    refreshLiverMarketEventsTable,
    runLiverMarketEventsCalculation,
    saveLiverMarketEvents,
} from "../../../services/apiService";
import HIVImpactCurveChart from "./MarketEventChart";
import HIVImpactCurveTable from "./MarketEventTable";

const globalConfigDateLocaleText = {
    fieldMonthPlaceholder: () => "MM",
    fieldYearPlaceholder: () => "YYYY",
};

const normalizeMetricsViews = (metricsViews = {}, fallbackMetricsViews = {}) => ({
    market_share:
        metricsViews.market_share ||
        metricsViews.payer_share ||
        metricsViews.product_share ||
        fallbackMetricsViews.market_share ||
        fallbackMetricsViews.payer_share ||
        fallbackMetricsViews.product_share ||
        {},
    market_volume:
        metricsViews.market_volume ||
        metricsViews.payer_volume ||
        metricsViews.product_volume ||
        fallbackMetricsViews.market_volume ||
        fallbackMetricsViews.payer_volume ||
        fallbackMetricsViews.product_volume ||
        {},
});

const normalizeMetricFilters = (metricFilters = []) =>
    (Array.isArray(metricFilters) ? metricFilters : []).map((item) => {
        const value =
            item?.value === "payer_share"
                ? "market_share"
                : item?.value === "payer_volume"
                    ? "market_volume"
                    : item?.value || "";

        const label =
            value === "market_share"
                ? "Market Share"
                : value === "market_volume"
                    ? "Market Volume"
                    : item?.label || value;

        return {
            ...item,
            label,
            value,
        };
    });

const getDefaultMetricValue = (metricFilters = []) =>
    metricFilters[0]?.value || "market_volume";

// The UI works with "market_share"/"market_volume" (see normalizeMetricFilters
// above), but the API's own vocabulary is "payer_share"/"payer_volume". Use
// this whenever building a payload to send back to the backend.
const denormalizeMetricValue = (value) =>
    value === "market_share"
        ? "payer_share"
        : value === "market_volume"
            ? "payer_volume"
            : value;

const sanitizeRunCalculationRow = (row = {}, selectedTab = "overall_event") => {
    const payloadRow = {
        event_name: row.event_name || "",
        start_date: row.start_date || "",
        peak_percent: Number(row.peak_percent || 0),
        months: Number(row.months || 0),
        curve_type: row.curve_type || "Linear",
        factor:
            row.curve_type === "Linear"
                ? 0
                : Number(row.factor || 0),
    };

    if (selectedTab !== "overall_event") {
        payloadRow.products = Array.isArray(row.products) ? row.products : [];
        payloadRow.payers = Array.isArray(row.markets) ? row.markets : [];
        payloadRow.source_percentages = row.source_percentages || {};

        if (selectedTab === "payer_event") {
            payloadRow.impacted_payers = Array.isArray(row.impacted_items)
                ? row.impacted_items
                : [];
        } else if (selectedTab === "product_event") {
            payloadRow.impacted_products = Array.isArray(row.impacted_items)
                ? row.impacted_items
                : [];
        }
    }

    return payloadRow;
};

const normalizeImpactCurveRowForUi = (row = {}) => ({
    ...row,
    products: Array.isArray(row.products) ? row.products : [],
    markets: Array.isArray(row.markets) ? row.markets : [],
    impacted_items: Array.isArray(row.impacted_items) ? row.impacted_items : [],
    source_percentages:
        row.source_percentages && typeof row.source_percentages === "object"
            ? row.source_percentages
            : {},
});

// The API nests an extra "sub view" layer under monthly/yearly for the
// market/payer and product tabs (e.g. product_level vs product_payer_level,
// or payer_level vs payer_product_level). The overall tab only has a single
// "overall_level" sub view. This helper figures out which sub view key is
// available/selected for a given raw monthly/yearly node.
const getAvailableSubViewKeys = (rawViewData = {}) =>
    Array.isArray(rawViewData?.view_options)
        ? rawViewData.view_options.map((option) => option.value).filter(Boolean)
        : [];

const getDefaultSubViewKey = (rawViewData = {}) => {
    const availableKeys = getAvailableSubViewKeys(rawViewData);

    if (rawViewData?.selected_view && availableKeys.includes(rawViewData.selected_view)) {
        return rawViewData.selected_view;
    }

    return availableKeys[0] || "";
};

// Resolves the raw monthly/yearly node down to the actual { chart, table }
// payload, drilling into the requested (or default) sub view when present.
const resolveMetricViewData = (rawViewData = {}, subViewKey = "") => {
    if (!rawViewData) {
        return {};
    }

    // Already flat (chart/table directly on this node) — nothing to drill into.
    if (rawViewData.chart || rawViewData.table) {
        return rawViewData;
    }

    const availableKeys = getAvailableSubViewKeys(rawViewData);

    if (!availableKeys.length) {
        return rawViewData;
    }

    const resolvedKey =
        (subViewKey && availableKeys.includes(subViewKey) && subViewKey) ||
        getDefaultSubViewKey(rawViewData);

    return resolvedKey ? rawViewData[resolvedKey] || {} : rawViewData;
};

const getMetricViewData = (tabData, metricName, viewName, subViewKey = "") => {
    const rawViewData = tabData?.metrics_views?.[metricName]?.[viewName] || {};
    return resolveMetricViewData(rawViewData, subViewKey);
};

const getDisplayMetricData = (
    activeTabName,
    payerTabData,
    productTabData,
    overallTabData,
    metricName,
    viewName,
    activeConfig = {},
    subViewKeysByTab = {},
) => {
    const payerMetricData = getMetricViewData(
        payerTabData,
        metricName,
        viewName,
        subViewKeysByTab.payer_event,
    );
    const productMetricData = getMetricViewData(
        productTabData,
        metricName,
        viewName,
        subViewKeysByTab.product_event,
    );
    const overallMetricData = getMetricViewData(
        overallTabData,
        metricName,
        viewName,
        subViewKeysByTab.overall_event,
    );

    if (activeTabName === "overall_event") {
        return overallMetricData;
    }

    if (activeTabName === "product_event") {
        return Object.keys(productMetricData || {}).length
            ? productMetricData
            : payerMetricData;
    }

    return Object.keys(payerMetricData || {}).length
        ? payerMetricData
        : productMetricData;
};

const normalizeEventTabs = (eventTabs = {}, fallbackTabs = {}) => {
    const payerTab = eventTabs.payer_event || {};
    const productTab = eventTabs.product_event || {};
    const overallTab = eventTabs.overall_event || {};

    const fallbackPayerTab = fallbackTabs.payer_event || {};
    const fallbackProductTab = fallbackTabs.product_event || {};
    const fallbackOverallTab = fallbackTabs.overall_event || {};

    const payerConfig = payerTab.impact_curve_configuration || {};
    const fallbackPayerConfig = fallbackPayerTab.impact_curve_configuration || {};
    const productConfig = productTab.impact_curve_configuration || {};
    const fallbackProductConfig = fallbackProductTab.impact_curve_configuration || {};
    const overallConfig = overallTab.impact_curve_configuration || {};
    const fallbackOverallConfig = fallbackOverallTab.impact_curve_configuration || {};

    return {
        payer_event: {
            ...fallbackPayerTab,
            ...payerTab,
            impact_curve_configuration: {
                ...fallbackPayerConfig,
                ...payerConfig,
                markets: payerConfig.markets || payerConfig.payers || fallbackPayerConfig.markets || fallbackPayerConfig.payers || [],
                impact_markets:
                    payerConfig.impact_markets || payerConfig.impact_payers || fallbackPayerConfig.impact_markets || fallbackPayerConfig.impact_payers || [],
            },
            metrics_views: normalizeMetricsViews(payerTab.metrics_views, fallbackPayerTab.metrics_views),
        },
        product_event: {
            ...fallbackProductTab,
            ...productTab,
            impact_curve_configuration: {
                ...fallbackProductConfig,
                ...productConfig,
                markets: productConfig.markets || productConfig.payers || fallbackProductConfig.markets || fallbackProductConfig.payers || [],
                impact_products:
                    productConfig.impact_products || fallbackProductConfig.impact_products || [],
            },
            metrics_views: normalizeMetricsViews(productTab.metrics_views, fallbackProductTab.metrics_views),
        },
        overall_event: {
            ...fallbackOverallTab,
            ...overallTab,
            impact_curve_configuration: {
                ...fallbackOverallConfig,
                ...overallConfig,
                markets: overallConfig.markets || overallConfig.payers || fallbackOverallConfig.markets || fallbackOverallConfig.payers || [],
            },
            metrics_views: normalizeMetricsViews(overallTab.metrics_views, fallbackOverallTab.metrics_views),
        },
    };
};

export default function HIVMarketEvent() {

    const { favState } = useContext(GlobalContext);

    const therapyArea =
        favState?.selectedTherapyArea || "HIV Treatment";

    const [availableMonths, setAvailableMonths] = useState([]);
    const [availableScenarios, setAvailableScenarios] = useState([]);
    const [metricFilters, setMetricFilters] = useState([]);

    const [eventTabsData, setEventTabsData] = useState({});

    const [scenarioName, setScenarioName] = useState("");

    const [selectedPayers, setSelectedPayers] = useState([]);
    const [selectedProducts, setSelectedProducts] = useState([]);

    const [fromDate, setFromDate] = useState("");
    const [toDate, setToDate] = useState("");

    // The "To Date" dropdown only lists months >= fromDate, but nothing
    // corrected `toDate` itself when a later `fromDate` pushed it out of
    // range — the Select would render blank while `toDate` silently kept
    // its old (now invalid, end < start) value, and that stale value still
    // got sent to Apply Filter. Keep it valid automatically instead.
    useEffect(() => {
        if (!fromDate || !toDate) return;

        if (dayjs(toDate).isBefore(dayjs(fromDate))) {
            setToDate(fromDate);
        }
    }, [fromDate]);

    const [activeTab, setActiveTab] =
        useState("overall_event");

    const isPayerEvent =
        activeTab === "payer_event";

    const isProductEvent =
        activeTab === "product_event";

    const isOverallEvent =
        activeTab === "overall_event";

    const [eventRows, setEventRows] =
        useState([]);

    // The backend never echoes back the rows we submit via "Run Calculation"
    // (impact_curve_configuration.rows always comes back empty), so the
    // effect below that re-seeds eventRows from the server data would wipe
    // out whatever the user just entered right after they click Run
    // Calculation. This ref lets that one action opt out of the reset,
    // while tab switches / the initial load / Apply Filter still resync
    // normally.
    const skipEventRowsResetRef = useRef(false);

    const [selectedMetric, setSelectedMetric] =
        useState("market_volume");

    const [selectedView, setSelectedView] =
        useState("monthly");

    // Tracks the nested sub-view selection per tab (e.g. "product_level" vs
    // "product_payer_level" for the Payer Event tab, "payer_level" vs
    // "payer_product_level" for the Product Event tab, and "overall_level"
    // for the Overall Event tab).
    const [selectedSubViewByTab, setSelectedSubViewByTab] = useState({
        payer_event: "",
        product_event: "",
        overall_event: "",
    });

    useEffect(() => {

        const rawViewData =
            eventTabsData?.[activeTab]
                ?.metrics_views?.[selectedMetric]?.[selectedView] || {};

        const availableKeys = getAvailableSubViewKeys(rawViewData);

        if (!availableKeys.length) return;

        setSelectedSubViewByTab((prev) => {
            const current = prev[activeTab];

            if (current && availableKeys.includes(current)) {
                return prev;
            }

            return {
                ...prev,
                [activeTab]: getDefaultSubViewKey(rawViewData),
            };
        });

    }, [activeTab, eventTabsData, selectedMetric, selectedView]);

    const handleSubViewChange = (nextSubView) => {
        setSelectedSubViewByTab((prev) => ({
            ...prev,
            [activeTab]: nextSubView,
        }));
    };

    useEffect(() => {

        if (!currentConfig) return;

        if (skipEventRowsResetRef.current) {
            skipEventRowsResetRef.current = false;
            return;
        }

        const rows = currentConfig.rows || [];

        setEventRows(
            rows.length
                ? rows.map((row) => normalizeImpactCurveRowForUi(row))
                : [createEmptyRow(currentConfig)]
        );

    }, [activeTab, eventTabsData]);

    const currentConfig =
        eventTabsData?.[activeTab]
            ?.impact_curve_configuration || {};

    const impactOptions =
        isPayerEvent
            ? currentConfig.impact_markets || currentConfig.markets || []
            : isProductEvent
                ? currentConfig.impact_products || currentConfig.products || []
                : [];

    const currentMetricData = getMetricViewData(
        eventTabsData?.[activeTab],
        selectedMetric,
        selectedView,
        selectedSubViewByTab[activeTab],
    );

    // Straight from the API response for the active tab/metric/granularity —
    // this is what should populate the "Product Level / Product-Payer Level"
    // (or "Payer Level / Payer-Product Level") dropdown above the table.
    const currentSubViewOptions =
        eventTabsData?.[activeTab]
            ?.metrics_views?.[selectedMetric]?.[selectedView]
            ?.view_options || [];

    const displayMetricData = getDisplayMetricData(
        activeTab,
        eventTabsData?.payer_event,
        eventTabsData?.product_event,
        eventTabsData?.overall_event,
        selectedMetric,
        selectedView,
        currentConfig,
        selectedSubViewByTab,
    );

    useEffect(() => {
        if (!metricFilters.length) return;

        const metricExists = metricFilters.some(
            (item) => item.value === selectedMetric
        );

        if (!metricExists) {
            setSelectedMetric(getDefaultMetricValue(metricFilters));
        }
    }, [metricFilters, selectedMetric]);

    const createEmptyRow = (config) => ({


        id: Date.now(),

        event_name: "",

        products: [],

        markets: [],

        impacted_items: [],

        source_percentages: {},

        start_date:
            config.forecast_start_date || "",

        peak_percent: "",

        months: "",

        curve_type:
            config.curve_types?.[0] || "",

        factor: "",

        enable_coverage: false,

    });

    const [menuAnchorEl, setMenuAnchorEl] =
        useState(null);

    const [selectedRowIndex, setSelectedRowIndex] =
        useState(null);

    const [openDeleteDialog, setOpenDeleteDialog] =
        useState(false);

    const [openImpactDialog, setOpenImpactDialog] =
        useState(false);

    const [selectedImpactRowIndex, setSelectedImpactRowIndex] =
        useState(null);

    const [impactValues, setImpactValues] = useState({});

    useEffect(() => {
        fetchFilters();
    }, []);

    const fetchFilters = async () => {
        try {
            const response = await getLiverMarketEventsFilters("HCV");
            const apiData = response?.data || {};

            setAvailableScenarios(
                apiData.available_scenarios ||
                apiData.scenario_names ||
                []
            );

            setAvailableMonths(
                apiData.available_months ||
                []
            );

            const filter =
                apiData.selected_filter ||
                {};

            setScenarioName(filter.scenario_name || "Base");

            setSelectedPayers(
                Array.isArray(filter.payers)
                    ? filter.payers
                    : Array.isArray(filter.markets)
                        ? filter.markets
                        : filter.payer
                            ? [filter.payer]
                            : filter.market
                                ? [filter.market]
                                : []
            );

            setSelectedProducts(
                Array.isArray(filter.products)
                    ? filter.products
                    : filter.product
                        ? [filter.product]
                        : []
            );

            setFromDate(filter.start_date || "");
            setToDate(filter.end_date || "");

            const initialMetricFilters = normalizeMetricFilters(
                apiData.metric_filters || []
            );

            setMetricFilters(initialMetricFilters);

            setSelectedMetric((prevSelectedMetric) => {
                const allowedValues = initialMetricFilters.map((item) => item.value);

                return allowedValues.includes(prevSelectedMetric)
                    ? prevSelectedMetric
                    : getDefaultMetricValue(initialMetricFilters);
            });

            const applyResponse = await applyLiverMarketEventsFilters({
                ta_name: "HCV",
                selected_filter: filter,
            });

            const applyData = applyResponse?.data || {};

            const appliedMetricFilters = normalizeMetricFilters(
                applyData.metric_filters || apiData.metric_filters || []
            );

            const effectiveMetricFilters =
                appliedMetricFilters.length > 0
                    ? appliedMetricFilters
                    : initialMetricFilters;

            setMetricFilters(effectiveMetricFilters);

            setSelectedMetric((prevSelectedMetric) => {
                const allowedValues = effectiveMetricFilters.map((item) => item.value);

                return allowedValues.includes(prevSelectedMetric)
                    ? prevSelectedMetric
                    : getDefaultMetricValue(effectiveMetricFilters);
            });

            const normalizedTabs =
                applyData.event_tabs && Object.keys(applyData.event_tabs).length
                    ? normalizeEventTabs(applyData.event_tabs, apiData.event_tabs || {})
                    : null;

            setEventTabsData(
                normalizedTabs ||
                normalizeEventTabs(apiData.event_tabs || {}, apiData.event_tabs || {}) ||
                {}
            );
        } catch (error) {
            console.error("Failed to fetch liver market event filters", error);
            setAvailableScenarios([]);
            setAvailableMonths([]);
            setMetricFilters([]);
            setEventTabsData({});
        }
    };

    // Shared by both applyLiverMarketEventsFilters and refreshLiverMarketEventsTable
    // responses, since the refresh API turns out to return the exact same
    // full-payload shape (ta_name, available_scenarios, event_tabs, ...) as
    // apply-filters rather than a scoped fragment.
    const applyEventTabsApiResponse = (apiData = {}, fallbackSelectedFilter = {}) => {
        setAvailableScenarios(
            apiData.available_scenarios ||
            apiData.scenario_names ||
            availableScenarios
        );

        setAvailableMonths(
            apiData.available_months ||
            availableMonths
        );

        const normalizedMetricFilters = normalizeMetricFilters(
            apiData.metric_filters || metricFilters || []
        );

        const effectiveMetricFilters =
            normalizedMetricFilters.length > 0
                ? normalizedMetricFilters
                : metricFilters;

        setMetricFilters(effectiveMetricFilters);

        setSelectedMetric((prevSelectedMetric) => {
            const allowedValues = effectiveMetricFilters.map((item) => item.value);

            return allowedValues.includes(prevSelectedMetric)
                ? prevSelectedMetric
                : getDefaultMetricValue(effectiveMetricFilters);
        });

        const appliedFilter = apiData.selected_filter || fallbackSelectedFilter;

        setScenarioName(appliedFilter.scenario_name || scenarioName);
        setSelectedPayers(appliedFilter.payers || selectedPayers);
        setSelectedProducts(appliedFilter.products || selectedProducts);
        setFromDate(appliedFilter.start_date || fromDate);
        setToDate(appliedFilter.end_date || toDate);

        const normalizedTabs =
            apiData.event_tabs && Object.keys(apiData.event_tabs).length
                ? normalizeEventTabs(apiData.event_tabs, eventTabsData)
                : null;

        setEventTabsData(
            normalizedTabs
                ? normalizedTabs
                : normalizeEventTabs(apiData.event_tabs || {}, eventTabsData) || {}
        );
    };

    const handleApplyFilter = async () => {

        const taName = "HCV";

        const payload = {
            ta_name: taName,
            selected_filter: {
                scenario_name: scenarioName,
                payers: selectedPayers,
                products: selectedProducts,
                start_date: fromDate,
                end_date: toDate,
            },
        };

        try {
            const response = await applyLiverMarketEventsFilters(payload);
            const apiData = response?.data || {};

            applyEventTabsApiResponse(apiData, payload.selected_filter);
        } catch (error) {
            console.error("Failed to apply liver market event filters", error);
        }
    };

    // Called from the table's "Refresh" button (while editing a row's values).
    // Sends the in-progress edits to the backend so it can recalculate
    // everything (e.g. redistribute market share so totals still add up,
    // which can also shift payer_volume and other tabs/views) and applies
    // the recalculated response the same way an apply-filters response is
    // applied, since the two endpoints return an identical payload shape.
    const handleRefreshLiverMarketEventTable = async (editedTableRows, editedLabel) => {
        const payload = {
            ta_name: "HCV",
            selected_filter: {
                scenario_name: scenarioName,
                payers: selectedPayers,
                products: selectedProducts,
                start_date: fromDate,
                end_date: toDate,
            },
            selected_tab: activeTab,
            selected_metric: denormalizeMetricValue(selectedMetric),
            selected_view: selectedView,
            selected_table_view: selectedSubViewByTab[activeTab] || "",
            edited_table_rows: editedTableRows,
            edited_label: editedLabel || "",
        };

        const response = await refreshLiverMarketEventsTable(payload);
        const apiData = response?.data || {};

        applyEventTabsApiResponse(apiData, payload.selected_filter);
    };

    // Called from the table's "Save" button. By the time Save is clickable
    // the user has already hit Refresh (see the button's `disabled` logic,
    // which requires isRefreshed), and handleRefreshLiverMarketEventTable
    // has already written the recalculated response into eventTabsData —
    // so we persist straight from that state rather than re-deriving it
    // from the table rows.
    const buildSaveScenarioPayload = (nameToSave) => ({
        ta_name: "HCV",
        scenario_name: nameToSave,
        selected_filter: {
            scenario_name: nameToSave,
            payers: selectedPayers,
            products: selectedProducts,
            start_date: fromDate,
            end_date: toDate,
        },
        event_tabs: eventTabsData || {},
    });

    const getSaveErrorMessage = (error) =>
        error?.response?.data?.detail ||
        error?.message ||
        "Failed to save scenario.";

    const isBaseScenarioError = (error) =>
        /cannot save as ['"]?base['"]?/i.test(getSaveErrorMessage(error) || "");

    // Simple message-only modal, reused for things like the "Run Calculation
    // can't run on Base" block — no input needed, just an acknowledgement.
    const [infoDialog, setInfoDialog] = useState({
        open: false,
        title: "",
        message: "",
    });

    const openInfoDialog = (title, message) => {
        setInfoDialog({ open: true, title, message });
    };

    const closeInfoDialog = () => {
        setInfoDialog({ open: false, title: "", message: "" });
    };

    const RUN_CALCULATION_BASE_MESSAGE =
        "Run Calculation cannot be run on the Base scenario. Please select or create a scenario first.";

    const isRunCalculationBaseError = (error) =>
        /run calculation cannot be run on the base scenario/i.test(
            getSaveErrorMessage(error) || "",
        );

    // Resolved/rejected once the Save-As dialog is submitted or dismissed,
    // so the table's "Save" button can just `await` this whole flow.
    const saveScenarioResolverRef = useRef(null);

    const [saveScenarioDialog, setSaveScenarioDialog] = useState({
        open: false,
        name: "",
        error: "",
        submitting: false,
    });

    const openSaveAsDialog = () => {
        setSaveScenarioDialog({
            open: true,
            name: "",
            error: "",
            submitting: false,
        });
    };

    const closeSaveAsDialog = () => {
        setSaveScenarioDialog({
            open: false,
            name: "",
            error: "",
            submitting: false,
        });

        if (saveScenarioResolverRef.current) {
            saveScenarioResolverRef.current.reject(new Error("Save cancelled"));
            saveScenarioResolverRef.current = null;
        }
    };

    const handleConfirmSaveAsScenario = async () => {
        const trimmedName = saveScenarioDialog.name.trim();

        if (!trimmedName) {
            setSaveScenarioDialog((prev) => ({
                ...prev,
                error: "Please enter a scenario name.",
            }));
            return;
        }

        if (trimmedName.toLowerCase() === "base") {
            setSaveScenarioDialog((prev) => ({
                ...prev,
                error: "Cannot save as 'Base'. Please provide a different scenario name.",
            }));
            return;
        }

        setSaveScenarioDialog((prev) => ({ ...prev, submitting: true, error: "" }));

        try {
            await saveLiverMarketEvents(buildSaveScenarioPayload(trimmedName));

            setScenarioName(trimmedName);
            setAvailableScenarios((prev) =>
                prev.includes(trimmedName) ? prev : [...prev, trimmedName],
            );

            setSaveScenarioDialog({
                open: false,
                name: "",
                error: "",
                submitting: false,
            });

            if (saveScenarioResolverRef.current) {
                saveScenarioResolverRef.current.resolve();
                saveScenarioResolverRef.current = null;
            }
        } catch (error) {
            setSaveScenarioDialog((prev) => ({
                ...prev,
                submitting: false,
                error: getSaveErrorMessage(error),
            }));
        }
    };

    const handleSaveLiverMarketEventTable = async () => {
        if (scenarioName.trim().toLowerCase() === "base") {
            // Don't hit the API at all for "Base" — it's always rejected.
            // Go straight to asking the user for a new scenario name.
            return new Promise((resolve, reject) => {
                saveScenarioResolverRef.current = { resolve, reject };
                openSaveAsDialog();
            });
        }

        try {
            await saveLiverMarketEvents(buildSaveScenarioPayload(scenarioName));
            return;
        } catch (error) {
            if (!isBaseScenarioError(error)) {
                console.error("Failed to save liver market event scenario", error);
                throw error;
            }
        }

        // Fallback: the backend rejected the save as "Base" even though our
        // client-side check above didn't catch it (e.g. name only matches
        // after some other normalization) — ask the user for a new name.
        return new Promise((resolve, reject) => {
            saveScenarioResolverRef.current = { resolve, reject };
            openSaveAsDialog();
        });
    };

    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "170px",
        maxWidth: "260px",

        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
            overflow: "hidden",
        },
    };

    const labelStyle = {
        mb: 1,
        fontSize: "14px",
        fontWeight: 700,
        color: "#64748b",
    };

    const EVENT_TABS = [
        {
            label: "Overall Event",
            value: "overall_event",
        },
        {
            label: "Payer Event",
            value: "payer_event",
        },
        {
            label: "Product Event",
            value: "product_event",
        },
    ];



    const handleAddNewEvent = () => {
        setEventRows((prev) => [
            ...prev,
            createEmptyRow(currentConfig)
        ]);
    };

    const handleRunCalculation = async () => {
        if (scenarioName.trim().toLowerCase() === "base") {
            openInfoDialog("Run Calculation", RUN_CALCULATION_BASE_MESSAGE);
            return;
        }

        const payload = {
            ta_name: "HCV",
            selected_filter: {
                scenario_name: scenarioName,
                payers: selectedPayers,
                products: selectedProducts,
                start_date: fromDate,
                end_date: toDate,
            },
            selected_tab: activeTab,
            impact_curve_configuration: {
                rows: (eventRows || []).map((row) =>
                    sanitizeRunCalculationRow(row, activeTab)
                ),
            },
        };

        try {
            skipEventRowsResetRef.current = true;

            const response = await runLiverMarketEventsCalculation(payload);
            const apiData = response?.data || {};

            applyEventTabsApiResponse(apiData, payload.selected_filter);
        } catch (error) {
            skipEventRowsResetRef.current = false;

            if (isRunCalculationBaseError(error)) {
                openInfoDialog("Run Calculation", RUN_CALCULATION_BASE_MESSAGE);
                return;
            }

            console.error("Failed to run liver market event calculation", error);
        }
    };

    const handleDuplicateRow = () => {

        if (selectedRowIndex == null)
            return;

        const row = eventRows[selectedRowIndex];

        const updated = [...eventRows];

        updated.splice(
            selectedRowIndex + 1,
            0,
            {
                ...row,
                products: [...(row.products || [])],
                markets: [...(row.markets || [])],
                impacted_items: [
                    ...(row.impacted_items || []),
                ],
                source_percentages: {
                    ...(row.source_percentages || {}),
                },
            }
        );

        setEventRows(updated);

        setMenuAnchorEl(null);
    };

    const handleDeleteRow = () => {

        setEventRows((prev) =>
            prev.filter(
                (_, index) =>
                    index !== selectedRowIndex
            )
        );

        setOpenDeleteDialog(false);

        setMenuAnchorEl(null);
    };

    const handleOpenMenu = (
        event,
        index
    ) => {

        setMenuAnchorEl(
            event.currentTarget
        );

        setSelectedRowIndex(index);

    };

    const handleCloseMenu = () => {

        setMenuAnchorEl(null);

    };

    const handleOpenImpactDialog = (
        index
    ) => {

        setSelectedImpactRowIndex(index);

        const row = eventRows[index] || {};
        const initialImpactValues = {};

        (impactOptions || []).forEach((option) => {
            const optionValue = getOptionValue(option);
            initialImpactValues[optionValue] = Number(
                row.source_percentages?.[optionValue] || 0
            );
        });

        setImpactValues(initialImpactValues);

        setOpenImpactDialog(true);

    };

    const handleSaveImpactDialog = () => {
        if (selectedImpactRowIndex == null) {
            setOpenImpactDialog(false);
            return;
        }

        const selectedRow = eventRows[selectedImpactRowIndex] || {};

        const selectedItems = isPayerEvent
            ? selectedRow.markets || []
            : isProductEvent
                ? selectedRow.products || []
                : [];

        const impactedItems = (impactOptions || [])
            .map((option) => getOptionValue(option))
            .filter((optionValue) => !selectedItems.includes(optionValue));

        const sanitizedPercentages = impactedItems.reduce((accumulator, optionValue) => {
            accumulator[optionValue] = Number(impactValues[optionValue] || 0);
            return accumulator;
        }, {});

        const updatedRows = [...eventRows];
        updatedRows[selectedImpactRowIndex] = {
            ...updatedRows[selectedImpactRowIndex],
            impacted_items: impactedItems,
            source_percentages: sanitizedPercentages,
        };

        setEventRows(updatedRows);
        setOpenImpactDialog(false);
    };

    const handleCloseImpactDialog = () => {

        setOpenImpactDialog(false);

    };

    const handleRowChange = (
        index,
        field,
        value
    ) => {

        const updated = [...eventRows];

        updated[index] = {
            ...updated[index],
            [field]: value,
        };

        setEventRows(updated);

    };

    const tableInputStyle = {
        borderRadius: "8px",

        "& .MuiOutlinedInput-root": {
            height: "32px",
            borderRadius: "6px",
            backgroundColor: "#fff",
            fontSize: "13px",
        },
    };

    const tableSelectStyle = {
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

    const menuProps = {
        PaperProps: {
            sx: {
                maxHeight: 280,
                borderRadius: "8px",

                "& .MuiMenuItem-root": {
                    minHeight: 34,
                    fontSize: "13px",
                },
            },
        },
    };

    const getOptionValue = (option) =>
        typeof option === "string"
            ? option
            : option.value || option.name || "";

    const getOptionLabel = (option) =>
        typeof option === "string"
            ? option
            : option.label || option.name || option.value || "";

    const findOption = (options, value) =>
        (options || []).find((option) =>
            typeof option === "string"
                ? option === value
                : option.value === value || option.name === value,
        );

    const renderOptionValue = (selected, options, placeholder = "Select") => {
        if (!selected || (Array.isArray(selected) && selected.length === 0)) {
            return placeholder;
        }

        if (Array.isArray(selected)) {
            return selected
                .map((item) => {
                    const found = findOption(options, item);
                    return found ? getOptionLabel(found) : String(item);
                })
                .join(", ");
        }

        const found = findOption(options, selected);
        return found ? getOptionLabel(found) : String(selected);
    };

    const headerColumns = isOverallEvent
        ? "1fr 0.6fr 0.5fr 0.5fr 0.6fr 0.45fr 56px"
        : "1fr 0.9fr 0.9fr 1fr 0.75fr 0.55fr 0.55fr 0.75fr 0.6fr 56px";

    const headers = isOverallEvent
        ? [
            "Overall Event",
            "Start Date",
            "Peak %",
            "Months",
            "Curve",
            "Factor",
            
            "",
        ]
        : [
            isPayerEvent ? "Payer Event" : "Product Event",
            isPayerEvent ? "Products" : "Payers",
            isPayerEvent ? "Payers" : "Products",
            isPayerEvent
                ? "Impacted Payers"
                : "Impacted Products",
            "Start Date",
            "Peak %",
            "Months",
            "Curve",
            "Factor",
            
            "",
        ];

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

                    {/* THERAPY AREA */}

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

                            <Typography>
                                {therapyArea}
                            </Typography>

                        </Box>

                    </Box>

                    {/* Scenario */}

                    <Box>

                        <Typography sx={labelStyle}>
                            SCENARIO NAME
                        </Typography>

                        <FormControl sx={inputStyle}>

                            <Select
                                value={scenarioName}
                                onChange={(e) =>
                                    setScenarioName(
                                        e.target.value
                                    )
                                }
                            >

                                {availableScenarios.map((item) => (

                                    <MenuItem
                                        key={item}
                                        value={item}
                                    >
                                        {item}
                                    </MenuItem>

                                ))}

                            </Select>

                        </FormControl>

                    </Box>

                    {/* From */}

                    <Box>

                        <Typography sx={labelStyle}>
                            FROM DATE
                        </Typography>

                        <LocalizationProvider
                            dateAdapter={AdapterDayjs}
                            localeText={
                                globalConfigDateLocaleText
                            }
                        >

                            <FormControl sx={inputStyle}>

                                <Select
                                    value={fromDate}
                                    onChange={(e) =>
                                        setFromDate(
                                            e.target.value
                                        )
                                    }
                                     MenuProps={{
                                        PaperProps: {
                                            sx: {
                                                maxHeight: 300,
                                                width: 130,
                                                "& .MuiMenuItem-root": {
                                                    minHeight: 32,
                                                    fontSize: "15px",
                                                    py: 0.5,
                                                },
                                            },
                                        },
                                    }}
                                    renderValue={(selected) =>
                                        dayjs(selected).format(
                                            "MMM YY"
                                        )
                                    }
                                >

                                    {availableMonths.map((month) => (

                                        <MenuItem
                                            key={month}
                                            value={month}
                                        >
                                            {dayjs(month).format(
                                                "MMM YY"
                                            )}
                                        </MenuItem>

                                    ))}

                                </Select>

                            </FormControl>

                        </LocalizationProvider>

                    </Box>

                    {/* To */}

                    <Box>

                        <Typography sx={labelStyle}>
                            TO DATE
                        </Typography>

                        <LocalizationProvider
                            dateAdapter={AdapterDayjs}
                            localeText={
                                globalConfigDateLocaleText
                            }
                        >

                            <FormControl sx={inputStyle}>

                                <Select
                                    value={toDate}
                                    onChange={(e) =>
                                        setToDate(
                                            e.target.value
                                        )
                                    }
                                     MenuProps={{
                                        PaperProps: {
                                            sx: {
                                                maxHeight: 300,
                                                width: 130,
                                                "& .MuiMenuItem-root": {
                                                    minHeight: 32,
                                                    fontSize: "15px",
                                                    py: 0.5,
                                                },
                                            },
                                        },
                                    }}
                                    renderValue={(selected) =>
                                        dayjs(selected).format(
                                            "MMM YY"
                                        )
                                    }
                                >

                                    {availableMonths
                                        .filter((m) =>
                                            dayjs(m).isAfter(
                                                fromDate
                                            ) ||
                                            dayjs(m).isSame(
                                                fromDate
                                            )
                                        )
                                        .map((month) => (

                                            <MenuItem
                                                key={month}
                                                value={month}
                                            >
                                                {dayjs(month).format(
                                                    "MMM YY"
                                                )}
                                            </MenuItem>

                                        ))}

                                </Select>

                            </FormControl>

                        </LocalizationProvider>

                    </Box>

                    {/* Payer */}

                    <Box>

                        <Typography sx={labelStyle}>
                            PAYER FILTER
                        </Typography>

                        <FormControl sx={inputStyle}>

                            <Select
                                multiple
                                displayEmpty
                                value={selectedPayers}
                                onChange={(e) => {

                                    const value =
                                        e.target.value;

                                    if (
                                        value.includes(
                                            "SELECT_ALL"
                                        )
                                    ) {

                                        if (
                                            selectedPayers.length ===
                                            (currentConfig.markets || []).length
                                        ) {

                                            setSelectedPayers([]);

                                        } else {

                                            setSelectedPayers(
                                                currentConfig.markets || []
                                            );

                                        }

                                    } else {

                                        setSelectedPayers(
                                            value
                                        );

                                    }

                                }}
                                renderValue={(selected) => (
                                    <Box
                                        sx={{
                                            display: "inline-block",
                                            maxWidth: "170px",
                                            whiteSpace: "nowrap",
                                            overflow: "hidden",
                                            textOverflow: "ellipsis",
                                            verticalAlign: "middle",
                                        }}
                                    >
                                        {renderOptionValue(
                                            selected,
                                            currentConfig.markets || [],
                                            "Select"
                                        )}
                                    </Box>
                                )}
                            >

                                <MenuItem value="SELECT_ALL">

                                    <Checkbox
                                        checked={
                                            selectedPayers.length ===
                                            (currentConfig.markets || []).length
                                        }
                                        indeterminate={
                                            selectedPayers.length > 0 &&
                                            selectedPayers.length <
                                            (currentConfig.markets || []).length
                                        }
                                    />

                                    <ListItemText
                                        primary="Select All"
                                    />

                                </MenuItem>

                                {(currentConfig.markets || []).map((item) => {
                                    const optionValue = getOptionValue(item);
                                    const optionLabel = getOptionLabel(item);
                                    return (
                                        <MenuItem
                                            key={optionValue}
                                            value={optionValue}
                                        >
                                            <Checkbox
                                                checked={selectedPayers.includes(
                                                    optionValue
                                                )}
                                            />

                                            <ListItemText
                                                primary={optionLabel}
                                            />
                                        </MenuItem>
                                    );
                                })}

                            </Select>

                        </FormControl>

                    </Box>

                    {/* Product */}

                    <Box>

                        <Typography sx={labelStyle}>
                            PRODUCT FILTER
                        </Typography>

                        <FormControl sx={inputStyle}>

                            <Select
                                multiple
                                value={selectedProducts}
                                onChange={(e) => {

                                    const value =
                                        e.target.value;

                                    if (
                                        value.includes(
                                            "SELECT_ALL"
                                        )
                                    ) {

                                        if (
                                            selectedProducts.length ===
                                            (currentConfig.products || []).length
                                        ) {

                                            setSelectedProducts(
                                                []
                                            );

                                        } else {

                                            setSelectedProducts(
                                                currentConfig.products || []
                                            );

                                        }

                                    } else {

                                        setSelectedProducts(
                                            value
                                        );

                                    }

                                }}
                                renderValue={(selected) => (
                                    <Box
                                        sx={{
                                            display: "inline-block",
                                            maxWidth: "170px",
                                            whiteSpace: "nowrap",
                                            overflow: "hidden",
                                            textOverflow: "ellipsis",
                                            verticalAlign: "middle",
                                        }}
                                    >
                                        {renderOptionValue(
                                            selected,
                                            currentConfig.products || [],
                                            "Select"
                                        )}
                                    </Box>
                                )}
                            >

                                <MenuItem value="SELECT_ALL">

                                    <Checkbox

                                        checked={
                                            selectedProducts.length ===
                                            (currentConfig.products || []).length
                                        }
                                        indeterminate={
                                            selectedProducts.length >
                                            0 &&
                                            selectedProducts.length <
                                            (currentConfig.products || []).length
                                        }

                                    />

                                    <ListItemText
                                        primary="Select All"
                                    />

                                </MenuItem>

                                {(currentConfig.products || []).map((item) => {
                                    const optionValue = getOptionValue(item);
                                    const optionLabel = getOptionLabel(item);
                                    return (
                                        <MenuItem
                                            key={optionValue}
                                            value={optionValue}
                                        >
                                            <Checkbox
                                                checked={selectedProducts.includes(
                                                    optionValue
                                                )}
                                            />

                                            <ListItemText
                                                primary={optionLabel}
                                            />
                                        </MenuItem>
                                    );
                                })}

                            </Select>

                        </FormControl>

                    </Box>

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
                <Box sx={{ mt: 3 }}>

                    <Tabs
                        value={activeTab}
                        onChange={(_, value) => {
                            setActiveTab(value);

                            // Payer Event / Product Event should default to
                            // the "Share" view rather than whatever metric
                            // happened to be selected on the previous tab.
                            if (value === "payer_event" || value === "product_event") {
                                const hasShareMetric = metricFilters.some(
                                    (item) => item.value === "market_share",
                                );

                                if (hasShareMetric) {
                                    setSelectedMetric("market_share");
                                }
                            }
                        }}
                    >

                        {EVENT_TABS.map((tab) => (

                            <Tab
                                key={tab.value}
                                value={tab.value}
                                label={tab.label}
                            />

                        ))}

                    </Tabs>

                </Box>
                <Accordion
                    defaultExpanded
                    sx={{
                        mt: 2,
                        borderRadius: "12px !important",
                        border: "1px solid #D8DEE8",
                        boxShadow: "none",
                    }}
                >

                    <AccordionSummary
                        expandIcon={<ExpandMoreIcon />}
                    >

                        <Box
                            sx={{
                                width: "100%",
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                            }}
                        >

                            <Typography
                                sx={{
                                    fontWeight: 700,
                                }}
                            >
                                Impact Curve Configuration
                            </Typography>

                            <Box
                                sx={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "12px",
                                }}
                            >

                                <Box
                                    role="button"
                                    tabIndex={0}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleRunCalculation();
                                    }}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter" || e.key === " ") {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            handleRunCalculation();
                                        }
                                    }}
                                    sx={{
                                        height: "33px",
                                        display: "inline-flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        textTransform: "none",
                                        borderRadius: "8px",
                                        backgroundColor: "#4F46E5",
                                        px: 1.5,
                                        fontWeight: 600,
                                        color: "#fff",
                                        cursor: "pointer",
                                        userSelect: "none",
                                    }}
                                >
                                    Run Calculation
                                </Box>

                                <Box
                                    role="button"
                                    tabIndex={0}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleAddNewEvent();
                                    }}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter" || e.key === " ") {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            handleAddNewEvent();
                                        }
                                    }}
                                    sx={{
                                        height: "33px",
                                        display: "inline-flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        textTransform: "none",
                                        borderRadius: "8px",
                                        backgroundColor: "#4F46E5",
                                        px: 1.5,
                                        fontWeight: 600,
                                        whiteSpace: "nowrap",
                                        color: "#fff",
                                        cursor: "pointer",
                                        userSelect: "none",
                                    }}
                                >
                                    + Add New Event
                                </Box>
                            </Box>
                        </Box>
                    </AccordionSummary>

                    <AccordionDetails>

                        <Paper
                            sx={{
                                mt: 1,
                                border: "1px solid #D8DEE8",
                                borderRadius: "12px",
                                overflowX: "auto",
                                overflowY: "auto",
                                maxHeight: 380,
                                boxShadow: "none",
                            }}
                        >

                            {/* HEADER */}

                            <Box
                                sx={{
                                    display: "grid",
                                    gridTemplateColumns: headerColumns,
                                    gap: 2,
                                    px: 2,
                                    py: 1.5,
                                    backgroundColor: "#f8fafc",
                                    borderBottom: "1px solid #D8DEE8",
                                    minWidth: isOverallEvent ? 1100 : 1750,
                                }}
                            >

                                {headers.map((item) => (

                                    <Typography
                                        key={item}
                                        sx={{
                                            fontSize: 13,
                                            fontWeight: 700,
                                            color: "#64748b",
                                        }}
                                    >
                                        {item}
                                    </Typography>

                                ))}

                            </Box>

                            {/* ROWS */}

                            {eventRows.map((row, index) => (

                                <Box
                                    key={index}
                                    sx={{
                                        display: "grid",
                                        gridTemplateColumns: headerColumns,
                                        gap: 2,
                                        px: 2,
                                        py: 1.5,
                                        alignItems: "center",
                                        minWidth: isOverallEvent ? 1100 : 1750,
                                    }}
                                >

                                    {/* MARKET EVENT */}

                                    {isPayerEvent && (
                                        <>

                                            {/* EVENT */}

                                            <TextField
                                                value={row.event_name}
                                                placeholder="Payer Event"
                                                size="small"
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "event_name",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* PRODUCTS */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    multiple
                                                    MenuProps={menuProps}
                                                    value={row.products}
                                                    renderValue={(selected) =>
                                                        renderOptionValue(
                                                            selected,
                                                            currentConfig.products || [],
                                                            "Select"
                                                        )
                                                    }
                                                    onChange={(e) => {

                                                        const value = e.target.value;

                                                        if (value.includes("SELECT_ALL")) {

                                                            handleRowChange(
                                                                index,
                                                                "products",
                                                                row.products.length ===
                                                                    (currentConfig.products || []).length
                                                                    ? []
                                                                    : currentConfig.products || []
                                                            );

                                                        } else {

                                                            handleRowChange(
                                                                index,
                                                                "products",
                                                                value
                                                            );

                                                        }

                                                    }}
                                                >
                                                    <MenuItem value="SELECT_ALL">

                                                        <Checkbox
                                                            size="small"
                                                            checked={
                                                                row.products.length ===
                                                                (currentConfig.products || []).length
                                                            }
                                                            indeterminate={
                                                                row.products.length > 0 &&
                                                                row.products.length <
                                                                (currentConfig.products || []).length
                                                            }
                                                        />

                                                        <ListItemText primary="Select All" />

                                                    </MenuItem>

                                                    {(currentConfig.products || []).map((item) => {
                                                        const optionValue = getOptionValue(item);
                                                        const optionLabel = getOptionLabel(item);
                                                        return (
                                                            <MenuItem
                                                                key={optionValue}
                                                                value={optionValue}
                                                                sx={{
                                                                    py: 0.5,
                                                                }}
                                                            >

                                                                <Checkbox
                                                                    checked={row.products.includes(optionValue)}
                                                                    size="small"
                                                                />

                                                                <ListItemText
                                                                    primary={optionLabel}
                                                                />

                                                            </MenuItem>
                                                        );
                                                    })}

                                                </Select>

                                            </FormControl>

                                            {/* MARKETS */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    multiple
                                                    MenuProps={menuProps}
                                                    value={row.markets}
                                                    renderValue={(selected) =>
                                                        renderOptionValue(
                                                            selected,
                                                            currentConfig.markets || [],
                                                            "Select"
                                                        )
                                                    }
                                                    onChange={(e) => {

                                                        const value = e.target.value;

                                                        if (value.includes("SELECT_ALL")) {

                                                            handleRowChange(
                                                                index,
                                                                "markets",
                                                                row.markets.length ===
                                                                    (currentConfig.markets || []).length
                                                                    ? []
                                                                    : currentConfig.markets || []
                                                            );

                                                        } else {

                                                            handleRowChange(
                                                                index,
                                                                "markets",
                                                                value
                                                            );

                                                        }

                                                    }}
                                                >

                                                    <MenuItem value="SELECT_ALL">

                                                        <Checkbox
                                                            size="small"
                                                            checked={
                                                                row.markets.length ===
                                                                (currentConfig.markets || []).length
                                                            }
                                                            indeterminate={
                                                                row.markets.length > 0 &&
                                                                row.markets.length <
                                                                (currentConfig.markets || []).length
                                                            }
                                                        />

                                                        <ListItemText primary="Select All" />

                                                    </MenuItem>

                                                    {(currentConfig.markets || []).map((item) => {
                                                        const optionValue = getOptionValue(item);
                                                        const optionLabel = getOptionLabel(item);
                                                        return (
                                                            <MenuItem
                                                                key={optionValue}
                                                                value={optionValue}
                                                                sx={{
                                                                    py: 0.5,
                                                                }}
                                                            >

                                                                <Checkbox
                                                                    checked={row.markets.includes(optionValue)}
                                                                    size="small"
                                                                />

                                                                <ListItemText
                                                                    primary={optionLabel}
                                                                />

                                                            </MenuItem>
                                                        );
                                                    })}

                                                </Select>

                                            </FormControl>

                                            {/* IMPACTED */}

                                            <Button
                                                variant="outlined"
                                                onClick={() =>
                                                    handleOpenImpactDialog(index)
                                                }
                                                sx={{
                                                    textTransform: "none",
                                                    borderRadius: "6px",
                                                    height: "32px",
                                                    fontSize: "12px",
                                                    minWidth: "90px",
                                                }}
                                            >
                                                Edit Source
                                            </Button>

                                            {/* START DATE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.start_date}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "start_date",
                                                            e.target.value
                                                        )
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

                                            {/* PEAK */}

                                            <TextField
                                                size="small"
                                                value={row.peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* MONTHS */}

                                            <TextField
                                                size="small"
                                                value={row.months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* CURVE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.curve_type}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "curve_type",
                                                            e.target.value
                                                        )
                                                    }
                                                >

                                                    {(currentConfig.curve_types || []).map((item) => (

                                                        <MenuItem
                                                            key={item}
                                                            value={item}
                                                        >
                                                            {item}
                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

                                            {/* FACTOR */}

                                            <TextField
                                                size="small"
                                                value={row.factor}
                                                disabled={
                                                    row.curve_type === "Linear"
                                                }
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "factor",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            row.curve_type === "Linear"
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* MENU */}

                                            <Box
                                                sx={{
                                                    display: "flex",
                                                    justifyContent: "center",
                                                    cursor: "pointer",
                                                }}
                                                onClick={(event) =>
                                                    handleOpenMenu(event, index)
                                                }
                                            >
                                                <MoreVertIcon fontSize="small" />
                                            </Box>

                                        </>
                                    )}

                                    {isProductEvent && (
                                        <>

                                            {/* PRODUCT EVENT */}

                                            <TextField
                                                value={row.event_name}
                                                placeholder="Product Event"
                                                size="small"
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "event_name",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* PAYERS */}
                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    multiple
                                                    MenuProps={menuProps}
                                                    value={row.markets}
                                                    renderValue={(selected) =>
                                                        renderOptionValue(
                                                            selected,
                                                            currentConfig.markets || [],
                                                            "Select"
                                                        )
                                                    }
                                                    onChange={(e) => {

                                                        const value = e.target.value;

                                                        if (value.includes("SELECT_ALL")) {

                                                            handleRowChange(
                                                                index,
                                                                "markets",
                                                                row.markets.length ===
                                                                    (currentConfig.markets || []).length
                                                                    ? []
                                                                    : currentConfig.markets || []
                                                            );

                                                        } else {

                                                            handleRowChange(
                                                                index,
                                                                "markets",
                                                                value
                                                            );

                                                        }

                                                    }}
                                                >

                                                    <MenuItem value="SELECT_ALL">

                                                        <Checkbox
                                                            size="small"
                                                            checked={
                                                                row.markets.length ===
                                                                (currentConfig.markets || []).length
                                                            }
                                                            indeterminate={
                                                                row.markets.length > 0 &&
                                                                row.markets.length <
                                                                (currentConfig.markets || []).length
                                                            }
                                                        />

                                                        <ListItemText primary="Select All" />

                                                    </MenuItem>

                                                    {(currentConfig.markets || []).map((item) => {
                                                        const optionValue = getOptionValue(item);
                                                        const optionLabel = getOptionLabel(item);
                                                        return (
                                                            <MenuItem
                                                                key={optionValue}
                                                                value={optionValue}
                                                                sx={{
                                                                    py: 0.5,
                                                                }}
                                                            >

                                                                <Checkbox
                                                                    checked={row.markets.includes(optionValue)}
                                                                    size="small"
                                                                />

                                                                <ListItemText
                                                                    primary={optionLabel}
                                                                />

                                                            </MenuItem>
                                                        );
                                                    })}

                                                </Select>

                                            </FormControl>

                                            {/* PRODUCTS */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    multiple
                                                    MenuProps={menuProps}
                                                    value={row.products}
                                                    renderValue={(selected) =>
                                                        renderOptionValue(
                                                            selected,
                                                            currentConfig.products || [],
                                                            "Select"
                                                        )
                                                    }
                                                    onChange={(e) => {

                                                        const value = e.target.value;

                                                        if (value.includes("SELECT_ALL")) {

                                                            handleRowChange(
                                                                index,
                                                                "products",
                                                                row.products.length ===
                                                                    (currentConfig.products || []).length
                                                                    ? []
                                                                    : currentConfig.products || []
                                                            );

                                                        } else {

                                                            handleRowChange(
                                                                index,
                                                                "products",
                                                                value
                                                            );

                                                        }

                                                    }}
                                                >

                                                    <MenuItem value="SELECT_ALL">

                                                        <Checkbox
                                                            size="small"
                                                            checked={
                                                                row.products.length ===
                                                                (currentConfig.products || []).length
                                                            }
                                                            indeterminate={
                                                                row.products.length > 0 &&
                                                                row.products.length <
                                                                (currentConfig.products || []).length
                                                            }
                                                        />

                                                        <ListItemText primary="Select All" />

                                                    </MenuItem>

                                                    {(currentConfig.products || []).map((item) => {
                                                        const optionValue = getOptionValue(item);
                                                        const optionLabel = getOptionLabel(item);
                                                        return (
                                                            <MenuItem
                                                                key={optionValue}
                                                                value={optionValue}
                                                                sx={{
                                                                    py: 0.5,
                                                                }}
                                                            >

                                                                <Checkbox
                                                                    checked={row.products.includes(optionValue)}
                                                                    size="small"
                                                                />

                                                                <ListItemText
                                                                    primary={optionLabel}
                                                                />

                                                            </MenuItem>
                                                        );
                                                    })}

                                                </Select>

                                            </FormControl>

                                            {/* IMPACTED PRODUCTS */}

                                            <Button
                                                variant="outlined"
                                                onClick={() =>
                                                    handleOpenImpactDialog(index)
                                                }
                                                sx={{
                                                    textTransform: "none",
                                                    borderRadius: "6px",
                                                    height: "32px",
                                                    fontSize: "12px",
                                                    minWidth: "90px",
                                                }}
                                            >
                                                Edit Source
                                            </Button>

                                            {/* START DATE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.start_date}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "start_date",
                                                            e.target.value
                                                        )
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

                                            {/* PEAK % */}

                                            <TextField
                                                size="small"
                                                value={row.peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* MONTHS */}

                                            <TextField
                                                size="small"
                                                value={row.months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* CURVE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.curve_type}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "curve_type",
                                                            e.target.value
                                                        )
                                                    }
                                                >

                                                    {(currentConfig.curve_types || []).map((item) => (

                                                        <MenuItem
                                                            key={item}
                                                            value={item}
                                                        >
                                                            {item}
                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

                                            {/* FACTOR */}

                                            <TextField
                                                size="small"
                                                value={row.factor}
                                                disabled={
                                                    row.curve_type === "Linear"
                                                }
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "factor",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            row.curve_type === "Linear"
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* MENU */}

                                            <Box
                                                sx={{
                                                    display: "flex",
                                                    justifyContent: "center",
                                                    cursor: "pointer",
                                                }}
                                                onClick={(event) =>
                                                    handleOpenMenu(event, index)
                                                }
                                            >
                                                <MoreVertIcon fontSize="small" />
                                            </Box>

                                        </>
                                    )}

                                    {isOverallEvent && (
                                        <>
                                            {/* OVERALL EVENT */}

                                            <TextField
                                                value={row.event_name}
                                                placeholder="Overall Event"
                                                size="small"
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "event_name",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* START DATE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.start_date}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "start_date",
                                                            e.target.value
                                                        )
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

                                            {/* PEAK % */}

                                            <TextField
                                                size="small"
                                                value={row.peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* MONTHS */}

                                            <TextField
                                                size="small"
                                                value={row.months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* CURVE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.curve_type}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "curve_type",
                                                            e.target.value
                                                        )
                                                    }
                                                >

                                                    {(currentConfig.curve_types || []).map((item) => (

                                                        <MenuItem
                                                            key={item}
                                                            value={item}
                                                        >
                                                            {item}
                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

                                            {/* FACTOR */}

                                            <TextField
                                                size="small"
                                                value={row.factor}
                                                disabled={
                                                    row.curve_type === "Linear"
                                                }
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "factor",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            row.curve_type === "Linear"
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* MENU */}

                                            <Box
                                                sx={{
                                                    display: "flex",
                                                    justifyContent: "center",
                                                    cursor: "pointer",
                                                }}
                                                onClick={(event) =>
                                                    handleOpenMenu(event, index)
                                                }
                                            >
                                                <MoreVertIcon fontSize="small" />
                                            </Box>

                                        </>
                                    )}

                                </Box>

                            ))}

                        </Paper>

                    </AccordionDetails>
                    <HIVImpactCurveChart
                        chartData={displayMetricData.chart || currentMetricData.chart}
                        activeTab={activeTab}
                    />

            </Accordion>

            <Accordion
                defaultExpanded
                sx={{
                    mt: 2,
                    borderRadius: "12px !important",
                    border: "1px solid #D8DEE8",
                    boxShadow: "none",
                }}
            >
                <AccordionSummary
                    expandIcon={<ExpandMoreIcon />}
                >
                    <Typography
                        sx={{
                            fontWeight: 700,
                        }}
                    >
                        Impact Curve Metrics Table
                    </Typography>
                </AccordionSummary>

                <AccordionDetails sx={{ p: 0 }}>
                    <HIVImpactCurveTable
                        tableData={displayMetricData.table || currentMetricData.table}
                        metricFilters={metricFilters}
                        selectedMetric={selectedMetric}
                        setSelectedMetric={setSelectedMetric}
                        selectedView={selectedView}
                        setSelectedView={setSelectedView}
                        activeTab={activeTab}
                        hierarchyView={selectedSubViewByTab[activeTab] || ""}
                        onHierarchyViewChange={handleSubViewChange}
                        subViewOptions={currentSubViewOptions}
                        onRefreshTable={handleRefreshLiverMarketEventTable}
                        onSaveTable={handleSaveLiverMarketEventTable}
                        selectedPayers={selectedPayers}
                        selectedProducts={selectedProducts}
                    />
                </AccordionDetails>
            </Accordion>

                <Menu
                    anchorEl={menuAnchorEl}
                    open={Boolean(menuAnchorEl)}
                    onClose={handleCloseMenu}
                >

                    <MenuItem
                        onClick={() => {
                            handleDuplicateRow();
                            handleCloseMenu();
                        }}
                    >
                        Duplicate
                    </MenuItem>

                    <MenuItem
                        sx={{
                            color: "error.main",
                        }}
                        onClick={() => {
                            setOpenDeleteDialog(true);
                            handleCloseMenu();
                        }}
                    >
                        Delete
                    </MenuItem>

                </Menu>
                <Dialog
                    open={openDeleteDialog}
                    onClose={() => setOpenDeleteDialog(false)}
                    maxWidth="xs"
                    fullWidth
                >

                    <DialogTitle>
                        Delete Event
                    </DialogTitle>

                    <DialogContent>

                        <Typography>
                            Are you sure you want to delete this event?
                        </Typography>

                    </DialogContent>

                    <DialogActions>

                        <Button
                            onClick={() =>
                                setOpenDeleteDialog(false)
                            }
                        >
                            Cancel
                        </Button>

                        <Button
                            color="error"
                            variant="contained"
                            onClick={handleDeleteRow}
                        >
                            Delete
                        </Button>

                    </DialogActions>

                </Dialog>
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

                        {isPayerEvent
                            ? "Impacted Payers (%)"
                            : "Impacted Products (%)"}

                        <IconButton
                            size="small"
                            onClick={handleCloseImpactDialog}
                        >
                            <CloseIcon fontSize="small" />
                        </IconButton>

                    </DialogTitle>
                    <DialogContent>

                        {(() => {
                            const selectedItems =
                                selectedImpactRowIndex !== null
                                    ? isPayerEvent
                                        ? eventRows[selectedImpactRowIndex]?.markets || []
                                        : isProductEvent
                                            ? eventRows[selectedImpactRowIndex]?.products || []
                                            : []
                                    : [];

                            const impactedOptionValues = (impactOptions || [])
                                .map((option) => getOptionValue(option))
                                .filter((optionValue) => !selectedItems.includes(optionValue));

                            const impactTotal = impactedOptionValues.reduce(
                                (sum, optionValue) => sum + Number(impactValues[optionValue] || 0),
                                0,
                            );

                            const isImpactValid =
                                impactedOptionValues.length === 0 ||
                                Math.abs(impactTotal - 100) < 0.0001;

                            return (
                                <>
                                    <Box
                                        sx={{
                                            mt: 1,
                                            display: "flex",
                                            flexDirection: "column",
                                            gap: 2,
                                        }}
                                    >
                                        {(impactOptions || []).map((item) => {
                                            const optionValue = getOptionValue(item);
                                            const optionLabel = getOptionLabel(item);
                                            const disabled = selectedItems.includes(optionValue);

                                            return (
                                                <Box
                                                    key={optionValue}
                                                    sx={{
                                                        display: "flex",
                                                        alignItems: "center",
                                                        gap: 7,
                                                    }}
                                                >
                                                    <Typography
                                                        sx={{
                                                            width: "120px",
                                                            flexShrink: 0,
                                                            fontSize: "14px",
                                                            color: disabled ? "#94A3B8" : "#334155",
                                                        }}
                                                    >
                                                        {optionLabel}
                                                    </Typography>

                                                    <TextField
                                                        type="number"
                                                        size="small"
                                                        disabled={disabled}
                                                        value={impactValues[optionValue] ?? 0}
                                                        onChange={(e) =>
                                                            setImpactValues((prev) => ({
                                                                ...prev,
                                                                [optionValue]: Number(e.target.value || 0),
                                                            }))
                                                        }
                                                        sx={{
                                                            width: "65px",
                                                            "& .MuiOutlinedInput-root": {
                                                                height: "30px",
                                                                fontSize: "13px",
                                                                backgroundColor: disabled ? "#E2E8F0" : "#fff",
                                                            },
                                                            "& input": {
                                                                padding: "6px 8px",
                                                            },
                                                        }}
                                                    />
                                                </Box>
                                            );
                                        })}

                                        {!isImpactValid && (
                                            <Typography
                                                sx={{
                                                    fontSize: "12px",
                                                    color: "#EF4444",
                                                    mt: 1,
                                                }}
                                            >
                                                Total must equal 100%.
                                            </Typography>
                                        )}
                                    </Box>

                                    <DialogActions
                                        sx={{
                                            p: 0,
                                            pt: 3,
                                        }}
                                    >
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
                                </>
                            );
                        })()}

                    </DialogContent>

                </Dialog>

                <Dialog
                    open={saveScenarioDialog.open}
                    onClose={closeSaveAsDialog}
                    PaperProps={{
                        sx: {
                            width: "360px",
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
                        Save as New Scenario

                        <IconButton
                            size="small"
                            onClick={closeSaveAsDialog}
                        >
                            <CloseIcon fontSize="small" />
                        </IconButton>
                    </DialogTitle>

                    <DialogContent>
                        <Typography
                            sx={{
                                fontSize: "13px",
                                color: "#64748b",
                                mb: 2,
                            }}
                        >
                            The "Base" scenario can't be overwritten. Give this scenario a
                            new name to save your changes.
                        </Typography>

                        <TextField
                            autoFocus
                            fullWidth
                            size="small"
                            placeholder="Scenario name"
                            value={saveScenarioDialog.name}
                            onChange={(e) =>
                                setSaveScenarioDialog((prev) => ({
                                    ...prev,
                                    name: e.target.value,
                                    error: "",
                                }))
                            }
                            onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                    handleConfirmSaveAsScenario();
                                }
                            }}
                            error={Boolean(saveScenarioDialog.error)}
                            helperText={saveScenarioDialog.error || ""}
                            sx={{
                                "& .MuiOutlinedInput-root": {
                                    borderRadius: "8px",
                                },
                            }}
                        />
                    </DialogContent>

                    <DialogActions sx={{ px: 3, pb: 3 }}>
                        <Button
                            onClick={closeSaveAsDialog}
                            sx={{ textTransform: "none" }}
                        >
                            Cancel
                        </Button>

                        <Button
                            variant="contained"
                            disabled={saveScenarioDialog.submitting}
                            onClick={handleConfirmSaveAsScenario}
                            sx={{
                                textTransform: "none",
                                borderRadius: "8px",
                                backgroundColor: "#4F46E5",
                            }}
                        >
                            {saveScenarioDialog.submitting ? "Saving..." : "Save"}
                        </Button>
                    </DialogActions>
                </Dialog>

                <Dialog
                    open={infoDialog.open}
                    onClose={closeInfoDialog}
                    PaperProps={{
                        sx: {
                            width: "380px",
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
                        {infoDialog.title || "Notice"}

                        <IconButton
                            size="small"
                            onClick={closeInfoDialog}
                        >
                            <CloseIcon fontSize="small" />
                        </IconButton>
                    </DialogTitle>

                    <DialogContent>
                        <Typography
                            sx={{
                                fontSize: "13px",
                                color: "#334155",
                            }}
                        >
                            {infoDialog.message}
                        </Typography>
                    </DialogContent>

                    <DialogActions sx={{ px: 3, pb: 3 }}>
                        <Button
                            variant="contained"
                            onClick={closeInfoDialog}
                            sx={{
                                textTransform: "none",
                                borderRadius: "8px",
                                backgroundColor: "#4F46E5",
                            }}
                        >
                            OK
                        </Button>
                    </DialogActions>
                </Dialog>
            </Paper>



        </Box>

    );
}