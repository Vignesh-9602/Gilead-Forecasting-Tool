import React from "react";

import {
    Box,
    Typography,
} from "@mui/material";

import Plot from "react-plotly.js";

const PlotComponent =
    Plot.default || Plot;

export default function MarketEventChart({
    chartData,
    activeTab,
}) {

    const title =
        activeTab === "product_event"
            ? "Product Event Impact Trend"
            : activeTab === "overall_event"
                ? "Overall Event Impact Trend"
                : "Payer Event Impact Trend";

    const {

        months,

        years,

        forecast_start_index,

        series = [],

    } = chartData || {};

    const MONTH_ABBREVIATIONS = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ];

    // Turns an ISO date string like "2020-06-01" into "Jun-20" for display.
    // Leaves anything that doesn't look like a YYYY-MM date (e.g. the plain
    // "2020" year headers used in yearly view) untouched.
    const formatMonthLabel = (value) => {
        if (typeof value !== "string") return value;

        const match = value.match(/^(\d{4})-(\d{2})/);

        if (!match) return value;

        const [, year, month] = match;
        const monthAbbr = MONTH_ABBREVIATIONS[Number(month) - 1] || month;

        return `${monthAbbr}-${year.slice(-2)}`;
    };

    const labels =
        (months || years || []).map(formatMonthLabel);

    const hasHistory = forecast_start_index > 0;

    const historyX =
        labels.slice(
            0,
            forecast_start_index
        );

    // When the selected date range excludes all historical months
    // (forecast_start_index === 0), there's no history point to anchor the
    // forecast line to — labels.slice(forecast_start_index - 1) would
    // otherwise become labels.slice(-1), which only grabs the LAST label
    // instead of the full range.
    const forecastX = hasHistory
        ? labels.slice(forecast_start_index - 1)
        : labels.slice(0);

    const traces = [];

    const allValues =
        series.flatMap((item) => [
            ...(item.history || []),
            ...(item.forecast || []),
        ]);

    const maxValue =
        Math.max(...allValues, 0);

    const yMax =
        Math.ceil(maxValue * 1.15);

    const getScenarioColor = (index) =>
        `hsl(${(index * 137.508) % 360}, 70%, 50%)`;

    const scenarioColorMap = React.useMemo(() => {
        const map = {};

        let index = 0;

        series.forEach((item) => {
            if (!map[item.scenario]) {
                map[item.scenario] = getScenarioColor(index++);
            }
        });

        return map;
    }, [series]);

    series.forEach((item) => {

        const color = scenarioColorMap[item.scenario] || getScenarioColor(0);

        traces.push({

            x: historyX,

            y: item.history,

            mode: "lines",

            name: item.label,

            line: {
                color,
                width: 3,
            }

        });

        // Anchor the dotted forecast line to the last history point so the
        // two lines connect visually — but only when a history point
        // actually exists (otherwise this prepends `undefined`, which
        // silently breaks the trace since x/y lengths would no longer
        // match forecastX above).
        const lastHistoryValue =
            hasHistory && item.history && item.history.length
                ? item.history[item.history.length - 1]
                : null;

        const forecastY =
            lastHistoryValue !== null
                ? [lastHistoryValue, ...(item.forecast || [])]
                : (item.forecast || []);

        traces.push({

            x: forecastX,

            y: forecastY,

            mode: "lines",

            name: `${item.label} Forecast`,

            line: {
                color,
                width: 3,
                dash: "dot",
            },

            showlegend: false,

        });

    });

    return (

        <Box
            sx={{
                mt: 3,
                border: "1px solid #D8DEE8",
                borderRadius: "12px",
                backgroundColor: "#fff",
                p: 2,
            }}
        >

            <Box
                sx={{
                    mb: 2,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: 2,
                }}
            >

                <Typography
                    sx={{
                        fontSize: "16px",
                        fontWeight: 700,
                        color: "#0f172a",
                    }}
                >
                    {title}
                </Typography>

            </Box>

                {!chartData || !series?.length ? (

                    <Box
                        sx={{
                            height: 50,
                            display: "flex",
                            justifyContent: "center",
                            alignItems: "center",
                            color: "#94a3b8",
                            fontSize: "14px",
                        }}
                    >
                        No chart data available. Please apply filters.
                    </Box>

                ) : (

                    <PlotComponent

                        data={traces}

                        layout={{

                            autosize: true,

                            height: 320,

                            margin: {
                                l: 50,
                                r: 20,
                                t: 10,
                                b: 70,
                            },

                            legend: {
                                orientation: "h",
                                x: 0,
                                y: -0.25,
                            },

                            xaxis: {
                                type: "category",
                                tickangle: -45,
                                showgrid: true,
                                gridcolor: "#F1F5F9",
                            },

                            yaxis: {
                                showgrid: false,
                                range: [0, yMax],
                            },

                            paper_bgcolor: "#ffffff",

                            plot_bgcolor: "#ffffff",

                        }}

                        config={{
                            responsive: true,
                            displayModeBar: false,
                        }}

                        style={{
                            width: "100%",
                        }}

                    />

                )}

        </Box>
    );

}