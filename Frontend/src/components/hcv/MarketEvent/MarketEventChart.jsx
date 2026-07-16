import React from "react";

import {
    Box,
    Typography,
    Paper,
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

    // const title =
    //     activeTab === "market_event"
    //         ? "Market Event Impact Trend"
    //         : activeTab === "product_event"
    //             ? "Product Event Impact Trend"
    //             : "Overall Event Impact Trend";

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

        <Paper
            elevation={0}
            sx={{
                m: 2,
                border: "1px solid #D8DEE8",
                borderRadius: "12px",
                overflow: "hidden",
            }}
        >

            <Box
                sx={{
                    px: 2.5,
                    py: 2,
                    // borderBottom:
                    //     "1px solid #E5E7EB",
                    backgroundColor: "#fff",
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

            <Box
                sx={{
                    p: 2,
                }}
            >

                {!chartData || !series?.length ? (

                    <Box
                        sx={{
                            height: 250,
                            display: "flex",
                            justifyContent: "center",
                            alignItems: "center",
                            color: "#94a3b8",
                            fontSize: "14px",
                        }}
                    >
                        No chart data available.
                    </Box>

                ) : (

                    <PlotComponent

                        data={traces}

                        layout={{

                            autosize: true,

                            height: 340,

                            margin: {
                                l: 55,
                                r: 20,
                                t: 10,
                                b: 65,
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

        </Paper>
    );

}