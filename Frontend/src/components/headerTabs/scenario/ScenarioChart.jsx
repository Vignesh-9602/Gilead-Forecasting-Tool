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

    //  Build traces (NO dotted lines, single smooth line)
    const traces = series.map((item, idx) => {

        const x = allMonths;

        const y = [
            ...item.train_values,
            ...item.forecast_values,
        ];

        return {
            x,
            y,
            type: "scatter",
            mode: "lines",
            name: item.scenario,
            line: {
                width: 3,
            },
        };
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
                                    showgrid: true,
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