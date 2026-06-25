import React from "react";

import { Paper } from "@mui/material";

import Plot from "react-plotly.js";

const PlotComponent = Plot.default || Plot;

export default function HIVMarketChart({ chartData }) {

    if (!chartData) return null;

    const {
        months,
        forecast_start_index,
        series,
    } = chartData;

    const traces = series.flatMap((item) => {

        const historyMonths =
            months.slice(
                0,
                forecast_start_index
            );

        const forecastMonths = [

            months[
            forecast_start_index - 1
            ],

            ...months.slice(
                forecast_start_index
            )

        ];

        return [

            // HISTORY

            {

                x: historyMonths,

                y: item.history,

                type: "scatter",

                mode: "lines+markers",

                name: item.label,

                line: {
                    width: 3,
                },

                marker: {
                    size: 6,
                },

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

                mode: "lines+markers",

                showlegend: false,

                line: {
                    dash: "dot",
                    width: 3,
                },

                marker: {
                    size: 6,
                },

            },

        ];

    });

    const allValues = series.flatMap((item) => [

        ...item.history,

        ...item.forecast,

    ]);

    const maxValue = Math.max(...allValues);

    const minValue = Math.min(...allValues);

    return (

        <Paper

            sx={{

                borderRadius: "12px",

                border: "1px solid #D8DEE8",

                boxShadow: "none",

                p: 2,

            }}

        >

            <PlotComponent

                data={traces}

                layout={{

                    autosize: true,

                    height: 420,

                    margin: {

                        l: 60,

                        r: 30,

                        t: 20,

                        b: 70,

                    },

                    hovermode: "x unified",

                    plot_bgcolor: "#fff",

                    paper_bgcolor: "#fff",

                    legend: {

                        orientation: "h",

                        y: -0.25,

                        x: 0.35,

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

                            minValue * .9,

                            maxValue * 1.1,

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

    );

}