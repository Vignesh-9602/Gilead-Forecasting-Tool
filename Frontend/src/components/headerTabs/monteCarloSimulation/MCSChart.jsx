import React from "react";

import {
    Box,
    Paper,
    Typography,
    Table,
    TableBody,
    TableRow,
    TableCell,
} from "@mui/material";

import Plot from "react-plotly.js";

const PlotComponent = Plot.default || Plot;

const formatCurrency = (value) =>
    `$${Number(value).toLocaleString()}`;

export default function MCSChart({
    data,
}) {
    if (!data) return null;

    const { histogram, summary } = data;

    const ranges =
        histogram?.map(
            (item) => item.range
        ) || [];

    const counts =
        histogram?.map(
            (item) => item.count
        ) || [];

    const summaryRows = [
        [
            "Number of Simulations",
            summary?.number_of_simulations,
        ],
        [
            "Mean Revenue",
            formatCurrency(
                summary?.mean_revenue
            ),
        ],
        [
            "Median Revenue",
            formatCurrency(
                summary?.median_revenue
            ),
        ],
        [
            "Std Dev Revenue",
            formatCurrency(
                summary?.std_dev_revenue
            ),
        ],
        [
            "Min Revenue",
            formatCurrency(
                summary?.min_revenue
            ),
        ],
        [
            "Max Revenue",
            formatCurrency(
                summary?.max_revenue
            ),
        ],
        [
            "5th Percentile",
            formatCurrency(
                summary?.percentile_5
            ),
        ],
        [
            "25th Percentile",
            formatCurrency(
                summary?.percentile_25
            ),
        ],
        [
            "75th Percentile",
            formatCurrency(
                summary?.percentile_75
            ),
        ],
        [
            "95th Percentile",
            formatCurrency(
                summary?.percentile_95
            ),
        ],
    ];

    return (
        <Box
            sx={{
                mt: 3,
                display: "grid",
                gridTemplateColumns:
                    "2.2fr 1fr",
                gap: 3,
            }}
        >
            {/* HISTOGRAM */}

            <Paper
                sx={{
                    p: 3,
                    borderRadius: "16px",
                    border:
                        "1px solid #D8DEE8",
                    boxShadow: "none",
                }}
            >
                <Typography
                    sx={{
                        textAlign: "center",
                        fontWeight: 700,
                        mb: 2,
                        fontSize: "20px",
                    }}
                >
                    Monte Carlo Revenue
                    Probability Distribution
                </Typography>

                <PlotComponent
                    data={[
                        {
                            x: ranges,
                            y: counts,
                            type: "bar",
                            hovertemplate:
                                "<b>%{x}</b><br>Count: %{y}<extra></extra>",
                            marker: {
                                color:
                                    "rgba(99,102,241,0.8)",
                                line: {
                                    color:
                                        "#4F46E5",
                                    width: 1,
                                },
                            },
                        },
                    ]}
                    layout={{
                        autosize: true,
                        height: 550,

                        margin: {
                            l: 60,
                            r: 20,
                            t: 20,
                            b: 120,
                        },

                        paper_bgcolor:
                            "white",

                        plot_bgcolor:
                            "white",

                        showlegend: false,

                        xaxis: {
                            title:
                                "Total Revenue Range (USD Millions)",
                            tickangle: -30,
                        },

                        yaxis: {
                            title:
                                "Frequency",
                            rangemode:
                                "tozero",
                        },
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

            {/* SUMMARY */}

            <Paper
                sx={{
                    borderRadius: "16px",
                    overflow: "hidden",
                    border:
                        "1px solid #D8DEE8",
                    boxShadow: "none",
                }}
            >
                <Box
                    sx={{
                        // background:
                        //     "#07122D",
                        color: "#000",
                        py: 2,
                        textAlign:
                            "center",
                        fontWeight: 700,
                        fontSize:
                            "18px",
                    }}
                >
                    SIMULATION RESULTS
                    SUMMARY
                </Box>

                <Table>
                    <TableBody>
                        {summaryRows.map(
                            (
                                [
                                    label,
                                    value,
                                ]
                            ) => (
                                <TableRow
                                    key={
                                        label
                                    }
                                >
                                    <TableCell>
                                        {
                                            label
                                        }
                                    </TableCell>

                                    <TableCell
                                        align="right"
                                        sx={{
                                            color:
                                                "#7573739a",
                                            fontWeight: 700,
                                        }}
                                    >
                                        {
                                            value
                                        }
                                    </TableCell>
                                </TableRow>
                            )
                        )}
                    </TableBody>
                </Table>
            </Paper>
        </Box>
    );
}