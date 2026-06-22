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
import DownloadIcon from "@mui/icons-material/Download";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import ExcelJS from "exceljs";
import { saveAs } from "file-saver";

const PlotComponent = Plot.default || Plot;

const formatCurrency = (value) =>
    `$${Number(value).toLocaleString(
        "en-US",
        {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }
    )}`;

export default function MCSChart({
    data,
    product,
    simulationIterations,
    confidenceInterval,
}) {
    if (!data) {
        return (
            <Paper
                sx={{
                    mt: 3,
                    p: 8,
                    borderRadius: "16px",
                    border: "1px solid #D8DEE8",
                    boxShadow: "none",
                    textAlign: "center",
                }}
            >
                {/* <Typography sx={{ fontSize: "48px", mb: 2 }}>
                    📊
                </Typography> */}

                <Typography
                    sx={{
                        fontSize: "20px",
                        fontWeight: 700,
                        color: "#334155",
                        mb: 1,
                    }}
                >
                    No Chart Data Available
                </Typography>

                <Typography
                    sx={{
                        color: "#64748B",
                    }}
                >
                    Run the Projection Engine to generate
                    simulation results and summary metrics.
                </Typography>
            </Paper>
        );
    }

    const { histogram, summary } = data;
    const peakBar = summary?.peak_bar;

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

    const handleDownloadExcel = async () => {
        if (!data) return;

        const workbook = new ExcelJS.Workbook();
        const worksheet = workbook.addWorksheet("Monte Carlo");

        // Filters
        worksheet.addRow(["Product", product]);
        worksheet.addRow([
            "Simulation Iterations",
            simulationIterations,
        ]);
        worksheet.addRow([
            "Confidence Interval",
            confidenceInterval,
        ]);
        worksheet.addRow([]);

        // Summary
        worksheet.addRow(["Simulation Summary"]);

        worksheet.addRow([
            "Number of Simulations",
            summary?.number_of_simulations,
        ]);

        worksheet.addRow([
            "Mean Revenue",
            summary?.mean_revenue,
        ]);

        worksheet.addRow([
            "Median Revenue",
            summary?.median_revenue,
        ]);

        worksheet.addRow([
            "Std Dev Revenue",
            summary?.std_dev_revenue,
        ]);

        worksheet.addRow([
            "Min Revenue",
            summary?.min_revenue,
        ]);

        worksheet.addRow([
            "Max Revenue",
            summary?.max_revenue,
        ]);

        worksheet.addRow([
            "5th Percentile",
            summary?.percentile_5,
        ]);

        worksheet.addRow([
            "25th Percentile",
            summary?.percentile_25,
        ]);

        worksheet.addRow([
            "75th Percentile",
            summary?.percentile_75,
        ]);

        worksheet.addRow([
            "95th Percentile",
            summary?.percentile_95,
        ]);

        worksheet.addRow([]);

        // Peak Bar
        if (summary?.peak_bar) {
            worksheet.addRow(["Peak Bar"]);

            worksheet.addRow([
                "Revenue Range",
                summary.peak_bar.revenue_range,
            ]);

            worksheet.addRow([
                "Mean Demand",
                summary.peak_bar.mean_demand,
            ]);

            worksheet.addRow([
                "Mean Compliance",
                summary.peak_bar.mean_compliance,
                // `${summary.peak_bar.mean_compliance}%`,
            ]);

            worksheet.addRow([
                "Price Per Vial",
                summary.peak_bar.price_per_vial,
            ]);

            worksheet.addRow([]);
        }

        // Histogram Table
        const histogramHeaderRow =
            worksheet.rowCount + 1;

        worksheet.addRow([
            "Revenue Range",
            "Count",
        ]);

        histogram.forEach((item) => {
            worksheet.addRow([
                item.range,
                item.count,
            ]);
        });

        // Styling
        worksheet.eachRow((row) => {
            row.eachCell((cell) => {
                cell.alignment = {
                    horizontal: "center",
                    vertical: "middle",
                };

                cell.border = {
                    top: { style: "thin" },
                    left: { style: "thin" },
                    bottom: { style: "thin" },
                    right: { style: "thin" },
                };
            });
        });

        worksheet.getRow(
            histogramHeaderRow
        ).font = {
            bold: true,
        };

        worksheet.getColumn(1).width = 30;
        worksheet.getColumn(2).width = 25;

        const buffer =
            await workbook.xlsx.writeBuffer();

        saveAs(
            new Blob([buffer]),
            `Monte_Carlo_${product}.xlsx`
        );
    };

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
                <Box
                    sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        mb: 2,
                    }}
                >
                    <Typography
                        sx={{
                            fontWeight: 700,
                            fontSize: "20px",
                        }}
                    >
                        Monte Carlo Revenue Probability Distribution
                    </Typography>

                    <Tooltip title="Download Results">
                        <IconButton onClick={handleDownloadExcel}>
                            <DownloadIcon />
                        </IconButton>
                    </Tooltip>
                </Box>

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
                            l: 80,
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

                {peakBar && (
                    <Box
                        sx={{
                            px: 2,
                            pb: 2,
                            borderBottom: "1px solid #E2E8F0",
                        }}
                    >
                        {/* <Typography
                            sx={{
                                fontSize: "13px",
                                fontWeight: 700,
                                color: "#64748B",
                                mb: 1,
                                textTransform: "uppercase",
                            }}
                        >
                            Peak Scenario
                        </Typography>

                        <Typography
                            sx={{
                                fontSize: "15px",
                                fontWeight: 700,
                                mb: 2,
                            }}
                        >
                            {peakBar.revenue_range}
                        </Typography> */}

                        <Box
                            sx={{
                                display: "flex",
                                justifyContent:
                                    "space-between",
                                mb: 1,
                            }}
                        >
                            <Typography
                                sx={{
                                    fontSize: "14px",
                                }}
                            >
                                Mean Demand
                            </Typography>

                            <Typography
                                sx={{
                                    fontWeight: 700,
                                    color: "#4F46E5",
                                }}
                            >
                                {Math.round(
                                    peakBar.mean_demand
                                ).toLocaleString()}
                            </Typography>
                        </Box>

                        <Box
                            sx={{
                                display: "flex",
                                justifyContent:
                                    "space-between",
                                mb: 1,
                            }}
                        >
                            <Typography
                                sx={{
                                    fontSize: "14px",
                                }}
                            >
                                Mean Compliance
                            </Typography>

                            <Typography
                                sx={{
                                    fontWeight: 700,
                                    color: "#4F46E5",
                                }}
                            >
                                {/* {Number(
                                    peakBar.mean_compliance
                                ).toFixed(3)} */}
                                {Number(peakBar.mean_compliance).toFixed(3)}%
                            </Typography>
                        </Box>

                        <Box
                            sx={{
                                display: "flex",
                                justifyContent:
                                    "space-between",
                            }}
                        >
                            <Typography
                                sx={{
                                    fontSize: "14px",
                                }}
                            >
                                Price Per Vial
                            </Typography>

                            <Typography
                                sx={{
                                    fontWeight: 700,
                                    color: "#4F46E5",
                                }}
                            >
                                {formatCurrency(
                                    peakBar.price_per_vial
                                )}
                            </Typography>
                        </Box>
                    </Box>
                )}

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