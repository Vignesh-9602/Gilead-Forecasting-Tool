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

export default function HIVOutputChart({ chartData, activeTab, selectedMarket, selectedProduct }) {

    // if (!chartData) return null;

    if (!chartData?.series?.length)
        return null;

    const labels =
        chartData.months ||
        chartData.years ||
        [];

    const {
        forecast_start_index,
        series,
    } = chartData;

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

    const ACTIVE_COLOR = "#F59E0B";   // Yellow
    const FADED_COLOR = "#D1D5DB";    // Gray
    const DEFAULT_COLOR = "#2563EB";  // Blue

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

        let color = ACTIVE_COLOR;
        let width = 3;

        switch (activeTab) {

            case "total_market_volume":
                color = ACTIVE_COLOR;
                width = 3;
                break;

            case "market_distribution": {
                const isSelected =
                    item.label?.toLowerCase() === selectedMarket?.toLowerCase();

                color = isSelected ? ACTIVE_COLOR : FADED_COLOR;
                width = isSelected ? 3 : 2;
                break;
            }

            case "product_distribution": {
                const isSelected =
                    item.label?.toLowerCase() === selectedProduct?.toLowerCase();

                color = isSelected ? ACTIVE_COLOR : FADED_COLOR;
                width = isSelected ? 3 : 2;
                break;
            }

            case "market_product": {
                const isSelected =
                    item.market?.toLowerCase() === selectedMarket?.toLowerCase() &&
                    item.product?.toLowerCase() === selectedProduct?.toLowerCase();

                color = isSelected ? ACTIVE_COLOR : FADED_COLOR;
                width = isSelected ? 3 : 2;
                break;
            }

            case "product_market": {
                const isSelected =
                    item.market?.toLowerCase() === selectedMarket?.toLowerCase() &&
                    item.product?.toLowerCase() === selectedProduct?.toLowerCase();

                color = isSelected ? ACTIVE_COLOR : FADED_COLOR;
                width = isSelected ? 3 : 2;
                break;
            }

            default:
                color = ACTIVE_COLOR;
                width = 3;
        }

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

    const allValues = series.flatMap((item) => [

        ...item.history,

        ...item.forecast,

    ]);

    const maxValue = Math.max(...allValues);

    const minValue = Math.min(...allValues);

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