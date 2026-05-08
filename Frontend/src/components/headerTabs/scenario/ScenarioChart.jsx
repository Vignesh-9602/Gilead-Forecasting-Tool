import React from "react";
import {
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Typography,
    Paper,
    Box,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import Plot from "react-plotly.js";

const PlotComponent = Plot.default || Plot;

export default function ScenarioChart({ chartData }) {

    const allMonths =
        chartData?.months?.map((month) =>
            new Date(month).toLocaleDateString("en-US", {
                month: "short",
                year: "2-digit",
            })
        ) || [];

    const forecastStartIndex = chartData?.forecast_start_index || 0;
    const series = chartData?.series || [];

    //  Build traces
    const BASE_COLOR = "#2563EB";

    const PLOTLY_COLORS = [
        "#EF553B",
        "#00CC96",
        "#AB63FA",
        "#FFA15A",
        "#19D3F3",
        "#FF6692",
        "#B6E880",
        "#FF97FF",
        "#FECB52",
    ];


    // Move BASE to end so it renders on TOP
    const orderedSeries = [
        ...series.filter((s) => s.scenario !== "BASE"),
        ...series.filter((s) => s.scenario === "BASE"),
    ];

    const traces = orderedSeries.flatMap((item, idx) => {

        // BASE always blue
        const color =
            item.scenario === "BASE"
                ? BASE_COLOR
                : PLOTLY_COLORS[idx % PLOTLY_COLORS.length];

        const trainX = allMonths.slice(0, forecastStartIndex);
        const trainY = item.train_values;

        const forecastX = [
            allMonths[forecastStartIndex - 1],
            ...allMonths.slice(forecastStartIndex),
        ];

        const forecastY = [
            item.train_values[item.train_values.length - 1],
            ...item.forecast_values,
        ];

        return [
            // Historical
            {
                x: trainX,
                y: trainY,
                type: "scatter",
                mode: "lines",
                name: item.scenario,
                legendgroup: item.scenario,
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
                name: item.scenario,
                legendgroup: item.scenario,
                showlegend: false,
                line: {
                    color,
                    width: 3,
                    dash: "dot",
                },
            },
        ];
    });

    //  Dynamic Y-axis scaling (same logic as ForecastTrend)
    const allValues = series.flatMap(item => [
        ...item.train_values,
        ...item.forecast_values
    ]);

    const maxValue = Math.max(...allValues, 0);
    const yMax = Math.ceil(maxValue * 1.15); // 15% headroom

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
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography sx={{ fontWeight: 700, fontSize: "16px" }}>
                    Visualization: Trends (Actuals vs. Projections)
                </Typography>
            </AccordionSummary>

            <AccordionDetails sx={{ pt: 0, pb: 1, px: 1 }}>
                {!chartData?.months?.length ? (
                    <Box
                        sx={{
                            mt: 3,
                            p: 4,
                            textAlign: "center",
                            color: "#94a3b8",
                            fontWeight: 500,
                        }}
                    >
                        No chart data available. Please select filters and apply.
                    </Box>
                ) : (
                    <Paper sx={{ boxShadow: "none" }}>
                        <PlotComponent
                            data={traces}
                            layout={{
                                autosize: true,
                                height: 350,
                                margin: {
                                    l: 50,
                                    r: 30,
                                    t: 5,
                                    b: 60,
                                },
                                legend: {
                                    orientation: "h",
                                    x: 0.35,
                                    y: -0.2,
                                },
                                showlegend: true,
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
                            style={{ width: "100%" }}
                            config={{
                                responsive: true,
                                displayModeBar: false,
                            }}
                        />
                    </Paper>
                )}
            </AccordionDetails>
        </Accordion>
    );
}