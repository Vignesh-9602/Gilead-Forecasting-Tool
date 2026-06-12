import React from "react";
import {
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Typography,
    Paper,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import Plot from "react-plotly.js";

const PlotComponent = Plot.default || Plot;

export default function RevenueChart({
    chartData,
}) {

    const months =
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

    const series =
        chartData?.series?.[0] || null;

    // No data state
    if (
        !chartData ||
        !chartData?.months?.length ||
        !series
    ) {
        return (
            <Accordion
                defaultExpanded
                sx={{
                    mt: 3,
                    borderRadius:
                        "12px !important",
                    border:
                        "1px solid #D8DEE8",
                    boxShadow: "none",
                    overflow: "hidden",
                }}
            >
                <AccordionSummary
                    expandIcon={
                        <ExpandMoreIcon />
                    }
                >
                    <Typography
                        sx={{
                            fontWeight: 700,
                            fontSize: "16px",
                        }}
                    >
                        Net Revenue Trend
                    </Typography>
                </AccordionSummary>

                <AccordionDetails>
                    <Paper
                        sx={{
                            p: 4,
                            textAlign: "center",
                            boxShadow: "none",
                        }}
                    >
                        No chart data available
                    </Paper>
                </AccordionDetails>
            </Accordion>
        );
    }

    const trainX = months.slice(
        0,
        forecastStartIndex
    );

    const trainY =
        series.train_values || [];

    const forecastX = [
        months[forecastStartIndex - 1],
        ...months.slice(
            forecastStartIndex
        ),
    ];

    const forecastY = [
        trainY[
        trainY.length - 1
        ],
        ...(series.forecast_values || []),
    ];

    const allValues = [
        ...trainY,
        ...(series.forecast_values || []),
    ];

    const yMax =
        allValues.length > 0
            ? Math.ceil(
                Math.max(
                    ...allValues
                ) * 1.15
            )
            : 100;

    return (
        <Accordion
            defaultExpanded
            sx={{
                mt: 3,
                borderRadius:
                    "12px !important",
                border:
                    "1px solid #D8DEE8",
                boxShadow: "none",
                overflow: "hidden",
            }}
        >
            <AccordionSummary
                expandIcon={
                    <ExpandMoreIcon />
                }
            >
                <Typography
                    sx={{
                        fontWeight: 700,
                        fontSize: "16px",
                    }}
                >
                    Net Revenue Trend
                </Typography>
            </AccordionSummary>

            <AccordionDetails>
                <Paper
                    sx={{
                        boxShadow: "none",
                    }}
                >
                    <PlotComponent
                        data={[
                            {
                                x: trainX,
                                y: trainY,
                                type: "scatter",
                                mode: "lines+markers",
                                name: "Net Revenue (History)",
                                hovertemplate:
                                    "<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
                                line: {
                                    color: "#2563EB",
                                    width: 3,
                                },
                            },
                            {
                                x: forecastX,
                                y: forecastY,
                                type: "scatter",
                                mode: "lines+markers",
                                name: "Net Revenue (Forecast)",
                                hovertemplate:
                                    "<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
                                line: {
                                    color: "#2563EB",
                                    width: 3,
                                    dash: "dot",
                                },
                            },
                        ]}
                        layout={{
                            autosize: true,
                            height: 400,

                            margin: {
                                l: 100,
                                r: 20,
                                t: 10,
                                b: 80,
                            },

                            legend: {
                                orientation: "h",
                                x: 0.35,
                                y: -0.2,
                            },

                            xaxis: {
                                title: "Month",
                                tickangle: -45,
                            },

                            yaxis: {
                                title:
                                    "Net Revenue ($)",
                                range: [
                                    0,
                                    yMax,
                                ],
                                tickprefix:
                                    "$",
                                separatethousands:
                                    true,
                                tickformat:
                                    ",.0f",
                            },

                            paper_bgcolor:
                                "white",

                            plot_bgcolor:
                                "white",
                        }}
                        style={{
                            width: "100%",
                        }}
                        config={{
                            responsive: true,
                            displayModeBar: false,
                        }}
                    />
                </Paper>
            </AccordionDetails>
        </Accordion>
    );
}