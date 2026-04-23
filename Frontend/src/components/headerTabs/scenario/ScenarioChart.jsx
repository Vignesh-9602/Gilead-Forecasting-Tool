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

    const trainValues = chartData?.train_values || [];
    const forecastStartIndex = chartData?.forecast_start_index || 0;

    const scenarios = chartData?.scenario_values || {};

    const trainX = allMonths.slice(0, forecastStartIndex);

    const forecastX = [
        allMonths[forecastStartIndex - 1],
        ...allMonths.slice(forecastStartIndex),
    ];

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

            <AccordionDetails sx={{ pt: 0 }}>
                {!chartData?.months?.length ? (
                    <Box sx={{ p: 4, textAlign: "center" }}>
                        No chart data available
                    </Box>
                ) : (
                    <Paper sx={{ boxShadow: "none" }}>
                        <PlotComponent
                            data={[
                                {
                                    x: trainX,
                                    y: trainValues,
                                    type: "scatter",
                                    mode: "lines",
                                    name: "Base Case (Actual)",
                                    line: {
                                        color: "#4f46e5",
                                        width: 3,
                                    },
                                },

                                ...Object.entries(scenarios).map(([name, values]) => ({
                                    x: forecastX,
                                    y: [trainValues[trainValues.length - 1], ...values],
                                    type: "scatter",
                                    mode: "lines",
                                    name,
                                    line: {
                                        dash: "dot",
                                        width: 3,
                                    },
                                })),
                            ]}
                            layout={{
                                autosize: true,
                                height: 420,
                                margin: {
                                    l: 50,
                                    r: 30,
                                    t: 10,
                                    b: 70,
                                },
                                legend: {
                                    orientation: "h",
                                    x: 0.2,
                                    y: 1.12,
                                },
                                xaxis: {
                                    tickangle: -45,
                                    showgrid: true,
                                },
                                yaxis: {
                                    showgrid: true,
                                },
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