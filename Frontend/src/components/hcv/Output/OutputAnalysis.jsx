import React, { useEffect, useRef, useState } from "react";
import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    IconButton,
    Tooltip,
} from "@mui/material";
import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
// import AnalysisChart from "./AnalysisChart";
import OutputChart from "./OutputChart";
import OutputTable from "./OutputTable";

const TABS = [
    { label: "Total Market Volume", value: "total_market_volume" },
    { label: "Payment Type Distribution (%)", value: "payment_type_distribution" },
    { label: "Product Distribution (%)", value: "product_distribution" },
    { label: "Payment Type-Payer-Product", value: "payment_type_payer_product" },
];

// The hierarchy tab's data sits one level deeper than the flat tabs —
// behind a selectable "ordering" (which dimension is outermost), e.g.
// outputAnalysis.payment_type_payer_product.<ordering>.<metric>.<view>.
// Tabs not listed here are flat: outputAnalysis.<tab>.<metric>.<view>.
// Mirrors ModelInput.jsx's hierarchyOrder concept for the equivalent tables.
const TAB_ORDERINGS = {
    payment_type_payer_product: [
        { label: "Payment Type-Payer-Product", value: "payment_type_payer_product" },
        { label: "Payment Type-Product-Payer", value: "payment_type_product_payer" },
        { label: "Product-Payment Type-Payer", value: "product_payment_type_payer" },
    ],
};

const DEFAULT_METRIC_BY_TAB = {
    total_market_volume: "payer_volume",
    payment_type_distribution: "payer_share",
    product_distribution: "payer_share",
    payment_type_payer_product: "payer_volume",
};

// Converts the API row shape ({ label, values, children }) into what
// OutputTable expects ({ key, label, values, level, rowType, children }).
const transformTableRows = (rows = [], parentKey = "row", level = 0) =>
    rows.map((row, index) => {
        const key = `${parentKey}-${index}`;
        const hasChildren = Array.isArray(row.children) && row.children.length > 0;

        return {
            key,
            label: row.label,
            values: row.values,
            level,
            isScenarioGroupRow: !!row.isScenarioGroupRow,
            rowType: row.isScenarioGroupRow ? "total" : hasChildren ? "group" : "child",
            children: hasChildren ? transformTableRows(row.children, key, level + 1) : undefined,
        };
    });

// The backend nests all tab data under each scenario name at the top
// level: outputAnalysis.<scenarioName>.market_analysis.<tab>[.<ordering>]
// .<metric>.<view>. Every scenario carries its own complete, independent
// tree — no scenario-suffixed labels to parse, unlike the response shape
// this screen was originally built against.
const getScenarioNode = (outputAnalysis, scenarioName, tab, ordering, metric, view) => {
    const tabNode = outputAnalysis?.[scenarioName]?.market_analysis?.[tab];
    if (!tabNode) return null;
    const node = ordering ? tabNode[ordering] : tabNode;
    return node?.[metric]?.[view] || null;
};

// Combines each selected scenario's chart into one, tagging every series
// with its scenario so lines from different scenarios stay distinguishable
// — same convention ModelInput uses ("<label> (<scenario>)"). Total Market
// Volume's series carries a generic label ("Total Market Volume") that
// doesn't vary by scenario at all, so it's replaced outright with the
// scenario name rather than appended to.
const buildCombinedChart = (outputAnalysis, scenarios, tab, ordering, metric, view) => {
    let months = [];
    let forecast_start_index = 0;
    const series = [];

    scenarios.forEach((scenarioName) => {
        const node = getScenarioNode(outputAnalysis, scenarioName, tab, ordering, metric, view);
        if (!node?.chart) return;
        if (!months.length) {
            months = node.chart.months || [];
            forecast_start_index = node.chart.forecast_start_index || 0;
        }
        (node.chart.series || []).forEach((s) => {
            const label =
                tab === "total_market_volume"
                    ? scenarioName
                    : scenarios.length > 1
                        ? `${s.label} (${scenarioName})`
                        : s.label;
            series.push({ ...s, label });
        });
    });

    return { months, forecast_start_index, series };
};

// Combines each selected scenario's table rows into one list. Total
// Market Volume renders flat — one row per scenario, no grouping, same
// as ModelInput.jsx (excluded from scenario-group nesting there too).
// Every other tab gets one group row per scenario, labeled with the
// scenario name, with that group's own aggregate sourced from its "Total"
// sibling row where one exists (flat tabs), or computed as the sum of its
// top-level children where it doesn't (the hierarchy tab has no separate
// Total row at all).
const buildCombinedRows = (outputAnalysis, scenarios, tab, ordering, metric, view, isPercent) => {
    if (tab === "total_market_volume") {
        return scenarios
            .map((scenarioName) => {
                const node = getScenarioNode(outputAnalysis, scenarioName, tab, ordering, metric, view);
                const row = node?.table?.rows?.[0];
                return row
                    ? { label: scenarioName, values: row.values || [], isScenarioGroupRow: true }
                    : null;
            })
            .filter(Boolean);
    }

    return scenarios
        .map((scenarioName) => {
            const node = getScenarioNode(outputAnalysis, scenarioName, tab, ordering, metric, view);
            const rows = node?.table?.rows || [];
            if (!rows.length) return null;

            const totalRow = rows.find((r) => (r.label || "").trim().toLowerCase() === "total");
            const childRows = totalRow ? rows.filter((r) => r !== totalRow) : rows;

            let groupValues;
            if (totalRow) {
                groupValues = totalRow.values;
            } else {
                const len = childRows.reduce((max, r) => Math.max(max, (r.values || []).length), 0);
                groupValues = Array.from({ length: len }, (_, i) =>
                    isPercent ? 100 : childRows.reduce((sum, r) => sum + (Number(r.values?.[i]) || 0), 0)
                );
            }

            return { label: scenarioName, values: groupValues, children: childRows, isScenarioGroupRow: true };
        })
        .filter(Boolean);
};

export default function OutputAnalysis({ outputAnalysis, metricFilters = [], selectedScenarios = [], selectedPaymentTypes = [], selectedPayers = [], selectedProducts = [] }) {
    const [activeTab, setActiveTab] = useState("total_market_volume");
    const [selectedMetricByTab, setSelectedMetricByTab] = useState(DEFAULT_METRIC_BY_TAB);
    const selectedMetric = selectedMetricByTab[activeTab] ?? DEFAULT_METRIC_BY_TAB[activeTab];
    const setSelectedMetric = (value) => {
        setSelectedMetricByTab((prev) => ({ ...prev, [activeTab]: value }));
    };
    const [viewMode, setViewMode] = useState("monthly");
    const tableRef = useRef(null);

    // Total Market Volume has no payment-type/payer/product dimensions for
    // rows to match against (rows are scenario names) — its highlighting is
    // its own concept, mirroring ModelInputTable.jsx's applied-scenario
    // radio button. Defaults to the first selected scenario so a row is
    // highlighted immediately rather than only after a manual click, and
    // re-defaults whenever the current selection no longer includes
    // whatever was highlighted (e.g. that scenario got deselected).
    const [highlightedScenario, setHighlightedScenario] = useState("");
    useEffect(() => {
        if (!selectedScenarios.includes(highlightedScenario)) {
            setHighlightedScenario(selectedScenarios[0] || "");
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedScenarios]);

    // Which ordering (dimension nesting order) is selected for tabs whose
    // data sits behind one — reset to that tab's first ordering whenever
    // the active tab changes, since orderings aren't shared across tabs.
    const orderings = TAB_ORDERINGS[activeTab];
    const [selectedOrdering, setSelectedOrdering] = useState(orderings?.[0]?.value || "");

    // Computed synchronously during render rather than trusting
    // selectedOrdering directly — a useEffect-driven reset lags one render
    // behind on tab switch (activeTab has already changed, but the effect
    // hasn't fired yet), which briefly makes selectedOrdering an empty
    // string/invalid value for the new tab and breaks the data lookup.
    // This guarantees a valid ordering on every render, no lag possible.
    const activeOrdering = orderings
        ? (orderings.some((o) => o.value === selectedOrdering) ? selectedOrdering : orderings[0].value)
        : null;

    useEffect(() => {
        if (orderings && activeOrdering !== selectedOrdering) {
            setSelectedOrdering(activeOrdering);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTab]);

    // table.type is a structural property (not per-scenario data), so it's
    // fine to read off just the first selected scenario.
    const firstScenarioNode = getScenarioNode(
        outputAnalysis, selectedScenarios[0], activeTab, activeOrdering, selectedMetric, viewMode
    );
    const isHierarchicalTable = firstScenarioNode?.table?.type === "hierarchy";

    const combinedChart = buildCombinedChart(
        outputAnalysis, selectedScenarios, activeTab, activeOrdering, selectedMetric, viewMode
    );
    const combinedRows = buildCombinedRows(
        outputAnalysis, selectedScenarios, activeTab, activeOrdering, selectedMetric, viewMode,
        selectedMetric === "payer_share"
    );
    const hasData = combinedChart.series.length > 0 || combinedRows.length > 0;

    const tableHeaders = combinedChart.months;
    const tableRows = transformTableRows(combinedRows);

    const activeTabLabel = TABS.find((t) => t.value === activeTab)?.label || "Output Table";

    // The table's first-column header text is a different thing from the
    // section title above it — ModelInputTable.jsx always heads that
    // column "Scenario" on the total-market tab (its rows are scenario
    // names), while the section title bar above the table still reads the
    // full tab name ("Total Market Volume"). Other tabs' rows are
    // products/payers, so their column header keeps the tab label.
    // PaymentPayerProductTable.jsx heads its column "Scenario / Payment Type
    // / Payer / Product" (or whichever order is selected) — it isn't a
    // fixed tab label, it spells out the row hierarchy's dimension order.
    // Derived from the active ordering's own label so it always tracks
    // whichever ordering is currently selected, rather than duplicating
    // TAB_ORDERINGS' dimension names in a second place.
    const hierarchyPivotLabel =
        activeTab === "payment_type_payer_product"
            ? `Scenario / ${(orderings?.find((o) => o.value === activeOrdering)?.label || "").replace(/-/g, " / ")}`
            : activeTabLabel;

    const tablePivotLabel =
        activeTab === "payment_type_payer_product" ? hierarchyPivotLabel : "Scenario";


    return (
        <Paper sx={{ mt: 3, borderRadius: "16px", border: "1px solid #D8DEE8", boxShadow: "none", overflow: "hidden" }}>
            <Box sx={{ px: 3, pt: 3 }}><Typography sx={{ fontSize: 18, fontWeight: 700 }}>Output Analysis</Typography></Box>
            <Box sx={{ mt: 2, background: "#e2e8f0", borderBottom: "1px solid #D8DEE8", display: "flex", gap: .5, px: .5, pt: .5 }}>
                {TABS.map(tab => (
                    <Box key={tab.value} onClick={() => setActiveTab(tab.value)}
                        sx={{
                            px: 2, py: 1, cursor: "pointer", fontSize: 12, fontWeight: 600, borderRadius: "6px 6px 0 0", whiteSpace: "nowrap",
                            color: activeTab === tab.value ? "#4F46E5" : "#64748b",
                            background: activeTab === tab.value ? "white" : "transparent"
                        }}>
                        {tab.label}
                    </Box>
                ))}
            </Box>
            {hasData ?
                <Box sx={{ p: 3 }}>
                    <OutputChart
                        chartData={combinedChart}
                        activeTab={activeTab}
                        selectedPaymentTypes={selectedPaymentTypes}
                        selectedPayers={selectedPayers}
                        selectedProducts={selectedProducts}
                        highlightedScenario={highlightedScenario}
                    />

                    <Box
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            flexWrap: "wrap",
                            gap: 1.5,
                            px: 2,
                            py: 2,
                            mt: 3,
                            border: "1px solid #D8DEE8",
                            borderBottom: "none",
                            borderRadius: "8px 8px 0 0",
                            background: "#fff",
                        }}
                    >
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                            <Typography sx={{ fontSize: "16px", fontWeight: 700, color: "#1e293b" }}>
                                {activeTabLabel}
                            </Typography>

                            {tableRows.some((r) => Array.isArray(r.children) && r.children.length > 0) && (
                                <>
                                    <Tooltip title="Expand All">
                                        <IconButton size="small" onClick={() => tableRef.current?.expandAll()}>
                                            <UnfoldMoreIcon fontSize="small" />
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Collapse All">
                                        <IconButton size="small" onClick={() => tableRef.current?.collapseAll()}>
                                            <UnfoldLessIcon fontSize="small" />
                                        </IconButton>
                                    </Tooltip>
                                </>
                            )}
                        </Box>

                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                flexWrap: "wrap",
                                gap: 1.5,
                            }}
                        >
                            {orderings && (
                                <FormControl
                                    size="small"
                                    sx={{
                                        minWidth: 220,
                                        "& .MuiOutlinedInput-root": {
                                            height: "35px",
                                            borderRadius: "8px",
                                            background: "#fcfcfd",
                                        },
                                    }}
                                >
                                    <Select
                                        value={activeOrdering}
                                        onChange={(e) => setSelectedOrdering(e.target.value)}
                                    >
                                        {orderings.map((o) => (
                                            <MenuItem key={o.value} value={o.value}>
                                                {o.label}
                                            </MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>
                            )}

                            <FormControl
                                size="small"
                                sx={{
                                    minWidth: 160,
                                    "& .MuiOutlinedInput-root": {
                                        height: "35px",
                                        borderRadius: "8px",
                                        background: "#fcfcfd",
                                    },
                                }}
                            >
                                <Select
                                    value={selectedMetric}
                                    onChange={(e) => setSelectedMetric(e.target.value)}
                                >
                                    {metricFilters.map((item) => (
                                        <MenuItem key={item.value} value={item.value}>
                                            {item.label}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>

                            <Box
                                sx={{
                                    display: "flex",
                                    backgroundColor: "#E2E8F0",
                                    borderRadius: "10px",
                                    p: "2px",
                                }}
                            >
                                {[
                                    { label: "Monthly", value: "monthly" },
                                    { label: "Yearly", value: "yearly" },
                                ].map((tab) => (
                                    <Box
                                        key={tab.value}
                                        onClick={() => setViewMode(tab.value)}
                                        sx={{
                                            px: 2,
                                            py: 0.8,
                                            cursor: "pointer",
                                            fontSize: "13px",
                                            fontWeight: 600,
                                            borderRadius: "8px",
                                            backgroundColor: viewMode === tab.value ? "#fff" : "transparent",
                                            color: viewMode === tab.value ? "#4F46E5" : "#64748B",
                                            transition: ".2s",
                                        }}
                                    >
                                        {tab.label}
                                    </Box>
                                ))}
                            </Box>
                        </Box>
                    </Box>

                    <OutputTable
                        ref={tableRef}
                        pivotLabel={tablePivotLabel}
                        headers={tableHeaders}
                        rows={tableRows}
                        metric={selectedMetric}
                        selectedPaymentTypes={selectedPaymentTypes}
                        selectedPayers={selectedPayers}
                        selectedProducts={selectedProducts}
                        forecastStartIndex={combinedChart.forecast_start_index}
                        isHierarchical={isHierarchicalTable}
                        isScenarioSelectable={activeTab === "total_market_volume"}
                        highlightedScenario={highlightedScenario}
                        onSelectScenario={setHighlightedScenario}
                    />
                </Box>
                :
                <Paper sx={{ m: 3, minHeight: 300, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "none" }}>
                    <Typography>No Output Analysis Available</Typography>
                </Paper>}
        </Paper>
    );
}