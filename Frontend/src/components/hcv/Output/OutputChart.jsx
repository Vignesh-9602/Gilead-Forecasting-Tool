import React from "react";

import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Paper,
    Typography,
} from "@mui/material";

import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

import Plot from "react-plotly.js";

const PlotComponent = Plot.default || Plot;

const MONTH_ABBREVIATIONS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

// Turns an ISO date string like "2020-04" into "Apr-20" for the x-axis.
// Leaves plain years (e.g. "2020") untouched for the yearly view.
const formatMonthLabel = (value) => {
    if (typeof value !== "string") return value;

    const match = value.match(/^(\d{4})-(\d{2})/);

    if (!match) return value;

    const [, year, month] = match;
    const monthAbbr = MONTH_ABBREVIATIONS[Number(month) - 1] || month;

    return `${monthAbbr}-${year.slice(-2)}`;
};

export default function OutputChart({ chartData, activeTab, selectedPaymentTypes = [], selectedPayers = [], selectedProducts = [], highlightedScenario = "" }) {

    // if (!chartData) return null;

    if (!chartData?.series?.length)
        return null;

    const labels = (
        chartData.months ||
        chartData.years ||
        []
    ).map(formatMonthLabel);

    const {
        forecast_start_index,
        series: allSeries,
    } = chartData;

    // Every tab except Total Market Volume should only chart entities
    // currently selected in the filter panel — but keep every scenario for
    // those entities (e.g. "Commercial (BASE)" and "Commercial (test-1)"
    // both stay). We don't know for certain which of payment type/payer/
    // product a given tab's series labels carry, so match by substring and
    // prefer the most specific combination that actually has matches:
    //   1. label contains a selected payment type AND payer AND product
    //   2. progressively less specific combinations
    //   3. last resort: show everything rather than an empty chart
    const containsTerm = (label, term) =>
        !!term && !!label && label.toLowerCase().includes(term.toLowerCase());

    const containsAny = (label, terms) =>
        Array.isArray(terms) && terms.some((term) => containsTerm(label, term));

    const activeDims = [
        selectedPaymentTypes,
        selectedPayers,
        selectedProducts,
    ].filter((terms) => terms.length > 0);

    const series = (() => {
        if (activeTab === "total_market_volume") return allSeries;

        const dims = activeDims;

        if (!dims.length) return allSeries;

        // Try requiring all active dimensions to match, then drop to fewer
        // until something actually matches.
        for (let requiredCount = dims.length; requiredCount >= 1; requiredCount--) {
            const matches = allSeries.filter((item) => {
                const matchedDims = dims.filter((terms) => containsAny(item.label, terms)).length;
                return matchedDims >= requiredCount;
            });
            if (matches.length) return matches;
        }

        return allSeries;
    })();

    // const colors = [
    //     "#2563EB",
    //     "#16A34A",
    //     "#DC2626",
    //     "#9333EA",
    //     "#EA580C",
    //     "#0891B2",
    //     "#D97706",
    //     "#4F46E5",
    // ];

    // Exact same color logic as ModelInputChart.jsx: getScenarioColor's
    // golden-angle HSL rotation for scenario-indexed coloring, with
    // CHART_PALETTE as the fallback for anything without an identifiable
    // scenario (mirrors ModelInputChart's getSeriesColor exactly).
    const getScenarioColor = (index) =>
        `hsl(${(index * 137.508) % 360}, 70%, 50%)`;

    const CHART_PALETTE = ["#4F46E5", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#06b6d4", "#3b82f6", "#ef4444"];

    // Series labels end in "(Scenario Name)" — e.g. "Commercial (BASE)" or
    // just "BASE" on the Total Market Volume tab (no parens at all). Pull
    // out whatever's in the trailing parens as the scenario name, falling
    // back to the full label when there's nothing to extract.
    const getScenarioName = (label) => {
        const match = label?.match(/\(([^)]+)\)\s*$/);
        return match ? match[1] : label;
    };

    // Build a stable scenario -> color map from the series currently being
    // charted, in the order each scenario first appears, so every line for
    // a given scenario (across every payer/product it might represent)
    // gets the same color, and different scenarios are always visually
    // distinct — this matters most now that filtering narrows most tabs
    // down to a single payer/product, where scenario is the only thing
    // left to tell lines apart.
    const scenarioColorMap = {};
    let nextColorIndex = 0;

    series.forEach((item) => {
        const scenario = getScenarioName(item.label);

        if (!(scenario in scenarioColorMap)) {
            scenarioColorMap[scenario] = getScenarioColor(nextColorIndex);
            nextColorIndex += 1;
        }
    });

    const getSeriesColor = (item, index) =>
        scenarioColorMap[getScenarioName(item.label)] || CHART_PALETTE[index % CHART_PALETTE.length];

    const traces = series.flatMap((item, index) => {

        const historyMonths =
            labels.slice(
                0,
                forecast_start_index
            );

        const forecastMonths = [

            labels[
            forecast_start_index - 1
            ],

            ...labels.slice(
                forecast_start_index
            )

        ];

        // Matches PaymentPayerProductTable.jsx's dimMatchesPath: a trace is
        // "highlighted" only when it matches every currently-active filter
        // dimension (payment type, payer, and/or product), not just some of
        // them — same amber-and-thicker treatment, same all-or-nothing bar.
        // Total Market Volume has no such dimensions (activeDims is empty
        // there) — it highlights whichever scenario is radio-selected
        // instead, same concept as ModelInputTable.jsx's applied-scenario
        // radio, and its series labels are bare scenario names already.
        const isHighlighted =
            activeTab === "total_market_volume"
                ? item.label === highlightedScenario
                : activeDims.length > 0 && activeDims.every((terms) => containsAny(item.label, terms));

        const color = isHighlighted ? "#f59e0b" : getSeriesColor(item, index);
        const width = isHighlighted ? 3.5 : 1.5;

        return [

            // HISTORY

            {

                x: historyMonths,

                y: item.history,

                type: "scatter",

                mode: "lines",

                name: item.label,

                line: {
                    color,
                    width,
                },

                // marker: {
                //     color,
                //     size: 6,
                // },

            },

            // FORECAST

            {

                x: forecastMonths,

                y: [

                    item.history[
                    item.history.length - 1
                    ],

                    ...item.forecast,

                ],

                type: "scatter",

                mode: "lines",

                name: item.label,

                showlegend: false,

                line: {
                    color,
                    dash: "dot",
                    width,
                },

                // marker: {
                //     color,
                //     size: 6,
                // },

            },

        ];

    });

    if (!series.length)
        return null;

    const allValues = series.flatMap((item) => [

        ...item.history,

        ...item.forecast,

    ]);

    const maxValue = allValues.length ? Math.max(...allValues) : 0;

    const minValue = allValues.length ? Math.min(...allValues) : 0;

    return (
        <Accordion
            defaultExpanded
            sx={{
                mt: 3,
                borderRadius: "12px !important",
                border: "1px solid #D8DEE8",
                boxShadow: "none",
                overflow: "hidden",
            }}
        >
            <AccordionSummary
                expandIcon={<ExpandMoreIcon />}
            >
                <Typography
                    sx={{
                        fontWeight: 700,
                        fontSize: "16px",
                    }}
                >
                    Market Analysis Chart
                </Typography>
            </AccordionSummary>

            <AccordionDetails
                sx={{
                    pt: 0,
                    pb: 1,
                    px: 1,
                }}
            >
                <Paper sx={{ boxShadow: "none" }}>
                    <PlotComponent

                        data={traces}

                        layout={{

                            autosize: true,

                            height: 350,

                            margin: {
                                l: 60,
                                r: 30,
                                t: 20,
                                b: 70,
                            },

                            // Plotly truncates hover trace names to 15
                            // characters by default; -1 shows the full name.
                            hoverlabel: {
                                namelength: -1,
                            },

                            // hovermode: "x unified",
                            plot_bgcolor: "#fff",
                            paper_bgcolor: "#fff",
                            legend: {
                                orientation: "h",
                                x: 0.5,
                                xanchor: "center",
                                y: -0.22,
                            },

                            xaxis: {

                                tickangle: -45,

                                showgrid: true,

                                gridcolor: "#F1F5F9",

                                zeroline: false,

                            },

                            yaxis: {

                                showgrid: true,

                                gridcolor: "#F1F5F9",

                                zeroline: false,

                                range: [
                                    Math.max(0, minValue * 0.9),
                                    maxValue === 0
                                        ? 10
                                        : maxValue * 1.1,
                                ],

                            },

                        }}

                        config={{

                            responsive: true,

                            displayModeBar: false,

                        }}

                        style={{

                            width: "100%",

                        }}

                    />

                </Paper>
            </AccordionDetails>
        </Accordion>

    );
};