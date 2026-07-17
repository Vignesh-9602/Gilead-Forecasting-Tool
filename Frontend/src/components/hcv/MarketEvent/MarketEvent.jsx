​import React, { useContext, useEffect, useState } from "react";

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
    IconButton,
    Switch
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
        fallbackMetricsViews.market_share ||
        fallbackMetricsViews.payer_share ||
        {},
    market_volume:
        metricsViews.market_volume ||
        metricsViews.payer_volume ||
        fallbackMetricsViews.market_volume ||
        fallbackMetricsViews.payer_volume ||
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

const cloneTableData = (tableData = {}) =>
    JSON.parse(JSON.stringify(tableData || {}));

const transposeHierarchyTable = (tableData = {}, selectedMetric = "market_volume") => {
    if (!tableData || tableData.type !== "hierarchy" || !Array.isArray(tableData.rows)) {
        return tableData || {};
    }

    const overallRows = [];
    const parentRows = [];

    tableData.rows.forEach((row) => {
        if (row?.label === "Overall" && !Array.isArray(row.children)) {
            overallRows.push(cloneTableData(row));
            return;
        }

        if (Array.isArray(row?.children) && row.children.length > 0) {
            parentRows.push(row);
        }
    });

    if (!parentRows.length) {
        return cloneTableData(tableData);
    }

    const columnCount =
        tableData.headers?.length ||
        parentRows[0]?.values?.length ||
        parentRows[0]?.children?.[0]?.values?.length ||
        0;

    const payerRows = new Map();
    const payerOrder = [];

    const ensurePayerRow = (payerLabel) => {
        if (!payerRows.has(payerLabel)) {
            payerRows.set(payerLabel, {
                label: payerLabel,
                values: Array(columnCount).fill(0),
                children: [],
            });
            payerOrder.push(payerLabel);
        }

        return payerRows.get(payerLabel);
    };

    parentRows.forEach((parentRow) => {
        (parentRow.children || []).forEach((childRow) => {
            ensurePayerRow(childRow.label);
        });
    });

    parentRows.forEach((parentRow) => {
        (parentRow.children || []).forEach((childRow) => {
            const payerRow = ensurePayerRow(childRow.label);
            payerRow.children.push({
                label: parentRow.label,
                values: Array.isArray(childRow.values)
                    ? [...childRow.values]
                    : Array(columnCount).fill(0),
            });
        });
    });

    payerOrder.forEach((payerLabel) => {
        const payerRow = payerRows.get(payerLabel);

        payerRow.values = Array.from({ length: columnCount }, (_, columnIndex) => {
            const sum = payerRow.children.reduce((accumulator, childRow) => {
                const numericValue = Number(childRow.values?.[columnIndex] ?? 0);
                return accumulator + (Number.isNaN(numericValue) ? 0 : numericValue);
            }, 0);

            return selectedMetric === "market_share"
                ? Number(sum.toFixed(2))
                : Math.round(sum);
        });
    });

    return {
        ...cloneTableData(tableData),
        rows: [
            ...overallRows,
            ...payerOrder.map((payerLabel) => payerRows.get(payerLabel)),
        ],
    };
};

const buildChartDataFromTable = (tableData = {}, selectedView = "monthly") => {
    if (!tableData || !Array.isArray(tableData.rows)) {
        return {};
    }

    const valueRows = tableData.rows.filter((row) => {
        if (!row || row.label === "Overall") {
            return false;
        }

        return Array.isArray(row.children) ? row.children.length > 0 : true;
    });

    const forecastStartIndex = tableData.forecast_start_index || 0;

    return {
        ...(selectedView === "yearly"
            ? { years: tableData.headers || [] }
            : { months: tableData.headers || [] }),
        forecast_start_index: forecastStartIndex,
        series: valueRows.map((row) => ({
            label: row.label,
            history: (row.values || []).slice(0, forecastStartIndex),
            forecast: (row.values || []).slice(forecastStartIndex),
        })),
    };
};

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

const getHierarchyTopLevelLabels = (tableData = {}) =>
    Array.isArray(tableData?.rows)
        ? tableData.rows
            .filter((row) => row?.label !== "Overall" && Array.isArray(row?.children) && row.children.length > 0)
            .map((row) => row.label)
        : [];

const shouldTransposeHierarchyTable = (
    tableData = {},
    desiredParentLabels = [],
    desiredChildLabels = [],
) => {
    if (!tableData || tableData.type !== "hierarchy" || !Array.isArray(tableData.rows)) {
        return false;
    }

    const topLevelLabels = getHierarchyTopLevelLabels(tableData);

    if (!topLevelLabels.length) {
        return false;
    }

    const parentMatches = topLevelLabels.filter((label) => desiredParentLabels.includes(label)).length;
    const childMatches = topLevelLabels.filter((label) => desiredChildLabels.includes(label)).length;

    return childMatches > parentMatches;
};

const normalizeHierarchyTableForTab = (
    tableData = {},
    desiredParentLabels = [],
    desiredChildLabels = [],
    selectedMetric = "market_volume",
) => {
    if (!shouldTransposeHierarchyTable(tableData, desiredParentLabels, desiredChildLabels)) {
        return cloneTableData(tableData);
    }

    return transposeHierarchyTable(tableData, selectedMetric);
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
        const baseMetricData =
            Object.keys(productMetricData || {}).length
                ? productMetricData
                : payerMetricData;

        const resolvedTable = normalizeHierarchyTableForTab(
            baseMetricData.table,
            activeConfig.products || [],
            activeConfig.markets || activeConfig.payers || [],
            metricName,
        );

        return {
            ...baseMetricData,
            table: resolvedTable,
            chart: buildChartDataFromTable(resolvedTable, viewName),
        };
    }

    const baseMetricData =
        Object.keys(payerMetricData || {}).length
            ? payerMetricData
            : productMetricData;

    const resolvedTable = normalizeHierarchyTableForTab(
        baseMetricData.table,
        activeConfig.markets || activeConfig.payers || [],
        activeConfig.products || [],
        metricName,
    );

    return {
        ...baseMetricData,
        table: resolvedTable,
        chart: buildChartDataFromTable(resolvedTable, viewName),
    };
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

        const rows = currentConfig.rows || [];

        setEventRows(
            rows.length
                ? rows
                : [createEmptyRow(currentConfig)]
        );

    }, [activeTab, eventTabsData]);

    const currentConfig =
        eventTabsData?.[activeTab]
            ?.impact_curve_configuration || {};

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

        start_date:
            config.forecast_start_date || "",

        peak_percent: "",

        months: "",

        curve_type:
            config.curve_types?.[0] || "",

        factor: "",

        enable_coverage: false,

        coverage_peak_percent: "",

        coverage_curve:
            config.curve_types?.[0] || "Linear",

        coverage_factor: "",

        coverage_peak_months: "",

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

    const handleRunCalculation = () => {
        console.warn("Run calculation API is not implemented yet.");
        window.alert("Run calculation API is not implemented yet.");
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
                products: [...row.products],
                markets: [...row.markets],
                impacted_items: [
                    ...row.impacted_items,
                ],
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

        setOpenImpactDialog(true);

    };

    const handleCloseImpactDialog = () => {

        setOpenImpactDialog(false);

    };

    const handleRowChange = (
        index,
        field,
        value
    ) => {

        const defaultCurveType =
            currentConfig.curve_types?.[0] || "Linear";

        const updated = [...eventRows];

        updated[index] = {
            ...updated[index],
            [field]: value,
        };

        // Clear coverage values when Coverage is turned OFF
        if (field === "enable_coverage" && !value) {
            updated[index].coverage_peak_percent = "";
            updated[index].coverage_curve = "";
            updated[index].coverage_factor = "";
            updated[index].coverage_peak_months = "";
        }

        // Set default coverage curve when Coverage is turned ON
        if (
            field === "enable_coverage" &&
            value &&
            !updated[index].coverage_curve
        ) {
            updated[index].coverage_curve = defaultCurveType;
        }

        setEventRows(updated);

    };

    const handleImpactSelection = (
        value
    ) => {

        const updated = [...eventRows];

        updated[
            selectedImpactRowIndex
        ].impacted_items = value;

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
        ? "1fr 0.6fr 0.5fr 0.5fr 0.6fr 0.45fr 0.45fr 0.7fr 0.7fr 56px"
        : "1fr 0.9fr 0.9fr 1fr 0.75fr 0.55fr 0.55fr 0.75fr 0.6fr 0.55fr 0.7fr 0.8fr 0.65fr 0.8fr 56px";

    const headers = isOverallEvent
        ? [
            "Overall Event",
            "Start Date",
            "Peak %",
            "Months",
            "Curve",
            "Factor",
            "Coverage",
            "Coverage Peak %",
            "Coverage Peak Months",
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
            "Coverage",
            "Coverage Peak %",
            "Coverage Peak Months",
            "Coverage Curve",
            "Coverage Factor",
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
                        onChange={(_, value) =>
                            setActiveTab(value)
                        }
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

                                            <Switch
                                                size="small"
                                                checked={row.enable_coverage}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "enable_coverage",
                                                        e.target.checked
                                                    )
                                                }
                                            />

                                            {/* COVERAGE % */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE CURVE */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE CURVE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                                disabled={!row.enable_coverage}
                                            >
                                                <Select
                                                    value={
                                                        row.coverage_curve ||
                                                        (currentConfig.curve_types?.[0] || "Linear")
                                                    }
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "coverage_curve",
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

                                            {/* COVERAGE FACTOR */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_factor}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_factor",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
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

                                            <Switch
                                                size="small"
                                                checked={row.enable_coverage}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "enable_coverage",
                                                        e.target.checked
                                                    )
                                                }
                                            />

                                            {/* COVERAGE PEAK % */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE CURVE */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE CURVE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                                disabled={!row.enable_coverage}
                                            >
                                                <Select
                                                    value={
                                                        row.coverage_curve ||
                                                        (currentConfig.curve_types?.[0] || "Linear")
                                                    }
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "coverage_curve",
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

                                            {/* COVERAGE FACTOR */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_factor}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_factor",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
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

                                            <Switch
                                                size="small"
                                                checked={row.enable_coverage}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "enable_coverage",
                                                        e.target.checked
                                                    )
                                                }
                                            />

                                            {/* COVERAGE PEAK % */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE PEAK MONTHS */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
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
                    maxWidth="sm"
                    fullWidth
                >
                    <DialogTitle
                        sx={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                        }}
                    >

                        {isPayerEvent
                            ? "Edit Impacted Payers"
                            : "Edit Impacted Products"}

                        <IconButton
                            onClick={handleCloseImpactDialog}
                        >
                            <CloseIcon />
                        </IconButton>

                    </DialogTitle>
                    <DialogContent>

                        <Typography
                            sx={{
                                mb: 2,
                                fontWeight: 600,
                            }}
                        >
                            Select impacted items
                        </Typography>

                        <FormControl fullWidth>

                            <Select
                                multiple
                                value={
                                    selectedImpactRowIndex !== null
                                        ? eventRows[selectedImpactRowIndex]
                                            ?.impacted_items || []
                                        : []
                                }
                                renderValue={(selected) =>
                                    renderOptionValue(
                                        selected,
                                        isPayerEvent
                                            ? currentConfig.impacted_markets || []
                                            : currentConfig.impacted_products || [],
                                        "Select"
                                    )
                                }
                                onChange={(e) =>
                                    handleImpactSelection(
                                        e.target.value
                                    )
                                }
                            >
                                {(isPayerEvent
                                    ? currentConfig.impacted_markets
                                    : currentConfig.impacted_products
                                )?.map((item) => {
                                    const optionValue = getOptionValue(item);
                                    const optionLabel = getOptionLabel(item);
                                    return (
                                        <MenuItem
                                            key={optionValue}
                                            value={optionValue}
                                        >

                                            <Checkbox
                                                checked={
                                                    selectedImpactRowIndex !==
                                                    null &&
                                                    eventRows[
                                                        selectedImpactRowIndex
                                                    ]?.impacted_items.includes(
                                                        optionValue
                                                    )
                                                }
                                            />

                                            <ListItemText
                                                primary={optionLabel}
                                            />

                                        </MenuItem>
                                    );
                                })}

                            </Select>

                        </FormControl>

                    </DialogContent>
                    <DialogActions>

                        <Button
                            onClick={handleCloseImpactDialog}
                        >
                            Cancel
                        </Button>

                        <Button
                            variant="contained"
                            onClick={handleCloseImpactDialog}
                        >
                            Apply
                        </Button>

                    </DialogActions>

                </Dialog>
            </Paper>


        </Box>

    );
}