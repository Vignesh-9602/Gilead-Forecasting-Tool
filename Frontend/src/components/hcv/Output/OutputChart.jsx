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

export default function OutputChart({ chartData, activeTab, selectedPayer, selectedProduct }) {

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

            case "payer_distribution": {
                // Series labels look like "Cash (BASE)" — strip the
                // trailing " (Scenario)" part before comparing to the
                // bare payer name the filter panel uses.
                const baseLabel = item.label?.split(" (")[0];
                const isSelected =
                    baseLabel?.toLowerCase() === selectedPayer?.toLowerCase();

                color = isSelected ? ACTIVE_COLOR : FADED_COLOR;
                width = isSelected ? 3 : 2;
                break;
            }

            case "product_distribution": {
                const baseLabel = item.label?.split(" (")[0];
                const isSelected =
                    baseLabel?.toLowerCase() === selectedProduct?.toLowerCase();

                color = isSelected ? ACTIVE_COLOR : FADED_COLOR;
                width = isSelected ? 3 : 2;
                break;
            }

            case "payer_product":
            case "product_payer": {
                // These tabs' chart series only carry a plain label like
                // "Commercial (BASE)" — no separate payer/product fields —
                // so match against either the selected payer or product.
                const baseLabel = item.label?.split(" (")[0];
                const isSelected =
                    baseLabel?.toLowerCase() === selectedPayer?.toLowerCase() ||
                    baseLabel?.toLowerCase() === selectedProduct?.toLowerCase();

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