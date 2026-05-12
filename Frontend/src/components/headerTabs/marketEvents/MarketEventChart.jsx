import React, { useMemo, useState } from "react";
import {
    Box,
    Typography,
    FormControl,
    Select,
    MenuItem,
} from "@mui/material";

import Plot from "react-plotly.js";

const PlotComponent = Plot.default || Plot;

export default function MarketEventChart() {

    const chartData = {
        months: [
            "2024-04-01",
            "2024-05-01",
            "2024-06-01",
            "2024-07-01",
            "2024-08-01",
            "2024-09-01",
            "2024-10-01",
            "2024-11-01",
            "2024-12-01",
            "2025-01-01",
            "2025-02-01",
            "2025-03-01",
            "2025-04-01",
            "2025-05-01",
            "2025-06-01",
            "2025-07-01",
            "2025-08-01",
            "2025-09-01",
            "2025-10-01",
            "2025-11-01",
            "2025-12-01",
            "2026-01-01",
            "2026-02-01",
            "2026-03-01",
            "2026-04-01",
        ],

        forecast_start_index: 22,

        series: [
            {
                lot: "1L",

                children: [
                    {
                        label: "Taxanes",

                        train_values: [
                            13, 12, 11, 10, 9, 8,
                            7, 6, 5, 4, 3, 2,
                            3, 4, 5, 6, 7, 8,
                            9, 10, 11, 12,
                        ],

                        forecast_values: [
                            13,
                            14,
                            15,
                        ],
                    },

                    {
                        label: "Trodelvy",

                        train_values: [
                            20, 21, 22, 23, 24, 25,
                            26, 27, 28, 29, 30, 31,
                            32, 33, 34, 35, 36, 37,
                            38, 39, 40, 41,
                        ],

                        forecast_values: [
                            42,
                            43,
                            44,
                        ],
                    },
                ],
            },

            {
                lot: "2L",

                children: [
                    {
                        label: "TPC",

                        train_values: [
                            10, 11, 12, 13, 14, 15,
                            16, 17, 18, 19, 20, 21,
                            22, 23, 24, 25, 26, 27,
                            28, 29, 30, 31,
                        ],

                        forecast_values: [
                            32,
                            33,
                            34,
                        ],
                    },
                ],
            },

            {
                lot: "3L+",

                children: [
                    {
                        label: "Enhertu",

                        train_values: [
                            8, 9, 10, 11, 12, 13,
                            14, 15, 16, 17, 18, 19,
                            20, 21, 22, 23, 24, 25,
                            26, 27, 28, 29,
                        ],

                        forecast_values: [
                            30,
                            31,
                            32,
                        ],
                    },
                ],
            },
        ],
    };

    const [selectedLot, setSelectedLot] =
        useState("1L");

    const availableLots =
        chartData?.series?.map(
            (item) => item.lot
        ) || [];

    const selectedLotData = useMemo(() => {
        return chartData?.series?.find(
            (item) => item.lot === selectedLot
        );
    }, [selectedLot]);

    const allMonths =
        chartData?.months?.map((month) =>
            new Date(month).toLocaleDateString(
                "en-US",
                {
                    month: "short",
                    year: "2-digit",
                }
            )
        ) || [];

    const forecastStartIndex =
        chartData?.forecast_start_index || 0;

    const PLOTLY_COLORS = [
        "#2563EB",
        "#EF4444",
        "#10B981",
        "#F59E0B",
        "#8B5CF6",
        "#EC4899",
    ];

    const traces =
        selectedLotData?.children?.flatMap(
            (item, idx) => {

                const color =
                    PLOTLY_COLORS[
                    idx % PLOTLY_COLORS.length
                    ];

                const trainX = allMonths.slice(
                    0,
                    forecastStartIndex
                );

                const trainY =
                    item.train_values;

                const forecastX = [
                    allMonths[
                    forecastStartIndex - 1
                    ],

                    ...allMonths.slice(
                        forecastStartIndex
                    ),
                ];

                const forecastY = [
                    item.train_values[
                    item.train_values.length - 1
                    ],

                    ...item.forecast_values,
                ];

                return [
                    // Actual
                    {
                        x: trainX,
                        y: trainY,

                        type: "scatter",
                        mode: "lines",

                        name: item.label,

                        legendgroup: item.label,

                        line: {
                            color,
                            width: 3,
                        },
                    },

                    // Forecast
                    {
                        x: forecastX,
                        y: forecastY,

                        type: "scatter",
                        mode: "lines",

                        name: item.label,

                        legendgroup: item.label,

                        showlegend: false,

                        line: {
                            color,
                            width: 3,
                            dash: "dot",
                        },
                    },
                ];
            }
        ) || [];

    const allValues =
        selectedLotData?.children?.flatMap(
            (item) => [
                ...item.train_values,
                ...item.forecast_values,
            ]
        ) || [];

    const maxValue = Math.max(...allValues, 0);

    const yMax = Math.ceil(maxValue * 1.15);

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
            {/* Header */}
            <Box
                sx={{
                    mb: 2,
                    display: "flex",
                    alignItems: "center",
                    justifyContent:
                        "space-between",
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
                    Market Event Impact Trend
                </Typography>

                {/* LOT FILTER */}
                <FormControl
                    size="small"
                    sx={{
                        minWidth: 120,

                        "& .MuiOutlinedInput-root":
                        {
                            height: "34px",
                            borderRadius: "8px",
                            fontSize: "13px",
                        },
                    }}
                >
                    <Select
                        value={selectedLot}
                        onChange={(e) =>
                            setSelectedLot(
                                e.target.value
                            )
                        }
                    >
                        {availableLots.map((lot) => (
                            <MenuItem
                                key={lot}
                                value={lot}
                            >
                                {lot}
                            </MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Box>

            <PlotComponent
                data={traces}
                layout={{
                    autosize: true,

                    height: 300,

                    margin: {
                        l: 50,
                        r: 30,
                        t: 10,
                        b: 60,
                    },

                    legend: {
                        orientation: "h",
                        x: 0,
                        y: -0.25,
                    },

                    xaxis: {
                        tickangle: -45,
                        showgrid: true,
                    },

                    yaxis: {
                        showgrid: false,
                        range: [0, yMax],
                    },

                    paper_bgcolor: "white",
                    plot_bgcolor: "white",
                }}
                style={{
                    width: "100%",
                }}
                config={{
                    responsive: true,
                    displayModeBar: false,
                }}
            />
        </Box>
    );
}