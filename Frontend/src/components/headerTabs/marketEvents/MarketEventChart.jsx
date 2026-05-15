import React, { useMemo, useState, useEffect } from "react";

import {
    Box,
    Typography,
    FormControl,
    Select,
    MenuItem,
} from "@mui/material";

import Plot from "react-plotly.js";

const PlotComponent = Plot.default || Plot;

export default function MarketEventChart({
    chartData,
}) {

    const availableLots = useMemo(() => {

        const lots =
            chartData?.series?.map(
                (item) => item.lot
            ) || [];

        return [...new Set(lots)];

    }, [chartData]);

    const [selectedLot, setSelectedLot] =
        useState("");

    // auto select first lot
    useEffect(() => {

        if (
            availableLots.length > 0 &&
            !selectedLot
        ) {
            setSelectedLot(availableLots[0]);
        }

    }, [availableLots]);

    const selectedLotSeries = useMemo(() => {

        return (
            chartData?.series?.filter(
                (item) => item.lot === selectedLot
            ) || []
        );

    }, [chartData, selectedLot]);

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
        selectedLotSeries.flatMap(
            (item, idx) => {

                const color =
                    PLOTLY_COLORS[
                    idx % PLOTLY_COLORS.length
                    ];

                const trainX =
                    allMonths.slice(
                        0,
                        forecastStartIndex
                    );

                const forecastX = [
                    allMonths[
                    forecastStartIndex - 1
                    ],

                    ...allMonths.slice(
                        forecastStartIndex
                    ),
                ];

                return [
                    // Actual
                    {
                        x: trainX,

                        y: item.train_values,

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

                        y: [
                            item.train_values[
                            item.train_values.length - 1
                            ],

                            ...item.forecast_values,
                        ],

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
        selectedLotSeries.flatMap(
            (item) => [
                ...item.train_values,
                ...item.forecast_values,
            ]
        ) || [];

    const maxValue =
        Math.max(...allValues, 0);

    const yMax =
        Math.ceil(maxValue * 1.15);

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
                    disabled={!chartData?.series?.length}
                >
                    <Select
                        value={selectedLot}
                        onChange={(e) =>
                            setSelectedLot(
                                e.target.value
                            )
                        }
                        displayEmpty
                    >
                        <MenuItem value="" disabled> LOTs </MenuItem>
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

            {!chartData?.series?.length ? (

                <Box
                    sx={{
                        height: 50,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "#94a3b8",
                        fontSize: "14px",
                    }}
                >
                    No chart data available.
                    Please apply filters.
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

            )}
        </Box>
    );
}