import React from "react";

import {
    Box,
    Typography,
} from "@mui/material";

import Plot from "react-plotly.js";

const PlotComponent =
    Plot.default || Plot;

export default function HIVImpactCurveChart({
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

    const labels =
        months || years || [];

    const historyX =
        labels.slice(
            0,
            forecast_start_index
        );

    const forecastX =
        labels.slice(
            forecast_start_index - 1
        );

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

    const COLORS = [
        "#2563EB",
        "#EF4444",
        "#10B981",
        "#F59E0B",
        "#8B5CF6",
        "#EC4899",
    ];

    series.forEach((item, index) => {

        const color =
            COLORS[index % COLORS.length];

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

        traces.push({

            x: forecastX,

            y: [
                item.history[
                item.history.length - 1
                ],
                ...item.forecast,
            ],

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