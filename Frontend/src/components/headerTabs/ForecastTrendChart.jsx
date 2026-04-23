import React, { useState, useEffect } from "react";
import {
    Paper,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Typography,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Button,
    Box,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import Plot from "react-plotly.js";
import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import { saveChanges } from "../../services/apiService";

const PlotComponent = Plot.default || Plot;

export default function ForecastTrendChart({
    therapyArea,
    indication,
    metric = "market_share",
    selectedProduct = "",
    selectedLot = "",
    chartData,
    tableData,
    updateChartData,
    updateTableData
}) {
    const allMonths =
        chartData?.months?.map((month) =>
            new Date(month).toLocaleDateString("en-US", {
                month: "short",
                year: "2-digit",
            })
        ) || [];

    const trainValues = chartData?.train_values || [];
    const forecastValues = chartData?.forecast_values || [];
    const forecastStartIndex = chartData?.forecast_start_index || 0;

    const [editable, setEditable] = useState(false);
    const [tableRows, setTableRows] = useState([]);
    const [originalRows, setOriginalRows] = useState([]);
    const [expandedLots, setExpandedLots] = useState({});
    const [lastEditedCell, setLastEditedCell] = useState(null);

    useEffect(() => {
        if (tableData?.length) {
            const clonedRows = JSON.parse(JSON.stringify(tableData));

            setTableRows(clonedRows);
            setOriginalRows(JSON.parse(JSON.stringify(clonedRows)));

            if (metric === "market_share") {
                const grouped = {};
                clonedRows.forEach((row) => {
                    grouped[row.lot] = true;
                });
                setExpandedLots(grouped);
            }
        }
    }, [tableData]); // remove metric from here

    useEffect(() => {
        // Reset immediately on metric change
        setTableRows([]);
        setOriginalRows([]);
        setExpandedLots({});
        setLastEditedCell(null);
        setEditable(false);
    }, [metric]);

    const toggleLot = (lot) => {
        setExpandedLots((prev) => ({
            ...prev,
            [lot]: !prev[lot],
        }));
    };

    const handleCellChange = (lotIndex, childIndex, colIndex, value) => {
        const updatedRows = JSON.parse(JSON.stringify(tableRows));

        if (updatedRows[lotIndex]?.children?.length) {
            updatedRows[lotIndex].children[childIndex].values[colIndex] =
                value === "" ? "" : Number(value);

            setLastEditedCell({
                lotIndex,
                childIndex,
                colIndex,
            });
        } else {
            // (for NPS fallback case if any)
            updatedRows[lotIndex].values[colIndex] =
                value === "" ? "" : Number(value);

            setLastEditedCell({
                rowIndex: lotIndex,
                colIndex,
            });
        }

        setTableRows(updatedRows);
        if (typeof updateTableData === "function") {
            updateTableData(updatedRows);
        }
    };

    const handleNormalize = () => {
        if (!lastEditedCell || metric !== "market_share") return;

        const updatedRows = JSON.parse(JSON.stringify(tableRows));

        const { lotIndex, childIndex, colIndex } = lastEditedCell;

        const editedLot = updatedRows[lotIndex];
        const editedRow = editedLot.children[childIndex];

        const editedValue = Number(editedRow.values[colIndex]);

        const otherRows = editedLot.children.filter(
            (_, idx) => idx !== childIndex
        );

        const otherTotal = otherRows.reduce(
            (sum, row) => sum + Number(row.values[colIndex]),
            0
        );

        const remaining = 100 - editedValue;

        let accumulated = 0;

        otherRows.forEach((row, idx) => {
            if (idx === otherRows.length - 1) {
                row.values[colIndex] = Number(
                    (remaining - accumulated).toFixed(2)
                );
            } else {
                const current = Number(row.values[colIndex]);

                const newValue = Number(
                    ((current / otherTotal) * remaining).toFixed(2)
                );

                row.values[colIndex] = newValue;
                accumulated += newValue;
            }
        });

        setTableRows(updatedRows);
    };

    const handleCancel = () => {
        setTableRows(JSON.parse(JSON.stringify(originalRows)));
        setEditable(false);
        setLastEditedCell(null);
    };

    // const handleSave = () => {
    //     setEditable(false);
    //     console.log("Saved rows:", tableRows);
    // };

    const trainX = allMonths.slice(0, forecastStartIndex);
    const trainY = trainValues;

    const forecastX = [
        allMonths[forecastStartIndex - 1],
        ...allMonths.slice(forecastStartIndex),
    ];

    const forecastY = [
        trainValues[trainValues.length - 1],
        ...forecastValues,
    ];

    const handleExpandAll = () => {
        const allExpanded = {};
        tableRows.forEach((row) => {
            allExpanded[row.lot] = true;
        });
        setExpandedLots(allExpanded);
    };

    const handleCollapseAll = () => {
        const allCollapsed = {};
        tableRows.forEach((row) => {
            allCollapsed[row.lot] = false;
        });
        setExpandedLots(allCollapsed);
    };

    const handleSave = async () => {
        try {
            const payload = {
                therapy_area: therapyArea,
                indication: indication,
                metric,
                product: selectedProduct,
                lot: selectedLot,
                table: tableRows, // directly send nested structure
            };

            const res = await saveChanges(payload);
            const data = res.data;

            // Update table (same structure)
            setTableRows(data.table);
            setOriginalRows(data.table);

            // Update chart
            if (typeof updateChartData === "function") {
                updateChartData(data.chart);
            }

            if (typeof updateTableData === "function") {
                updateTableData(data.table);
            }

            setEditable(false);
        } catch (error) {
            console.error("Save Changes API failed:", error);
        }
    };

    return (
        <>
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
                        Forecast Trend Chart
                    </Typography>
                </AccordionSummary>

                <AccordionDetails sx={{ pt: 0, pb: 1, px: 1 }}>
                    {!chartData?.months?.length ? (
                        <Box
                            sx={{
                                mt: 3,
                                p: 4,
                                textAlign: "center",
                                // height: 280,
                                // display: "flex",
                                // justifyContent: "center",
                                // alignItems: "center",
                                // color: "#94a3b8",
                                // fontSize: "15px",
                                fontWeight: 500,
                            }}
                        >
                            No chart data available. Please select filters and apply.
                        </Box>
                    ) : (
                        <Paper sx={{ boxShadow: "none" }}>
                            <PlotComponent
                                data={[
                                    {
                                        x: trainX,
                                        y: trainY,
                                        type: "scatter",
                                        mode: "lines",
                                        name: "Train Data",
                                        line: {
                                            color: "#f59e0b",
                                            width: 3,
                                        },
                                    },
                                    {
                                        x: forecastX,
                                        y: forecastY,
                                        type: "scatter",
                                        mode: "lines",
                                        name: "Forecast Data",
                                        line: {
                                            color: "#f59e0b",
                                            width: 3,
                                            dash: "dot",
                                        },
                                    },
                                ]}
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

            <Box
                sx={{
                    mt: 3,
                    mb: 1,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                }}
            >
                {/* LEFT SIDE ICONS */}
                <Box sx={{ display: "flex", gap: 1, minWidth: 80 }}>
                    {metric === "market_share" && (
                        <>
                            <Tooltip title="Expand All">
                                <IconButton onClick={handleExpandAll}>
                                    <UnfoldMoreIcon />
                                </IconButton>
                            </Tooltip>

                            <Tooltip title="Collapse All">
                                <IconButton onClick={handleCollapseAll}>
                                    <UnfoldLessIcon />
                                </IconButton>
                            </Tooltip>
                        </>
                    )}
                </Box>

                {/* RIGHT SIDE BUTTONS */}
                <Box sx={{ display: "flex", gap: 2 }}>
                    <Button
                        variant="outlined"
                        disabled={!tableRows.length}
                        onClick={() => setEditable(true)}
                    >
                        Edit Changes
                    </Button>

                    {metric === "market_share" && (
                        <Button
                            variant="outlined"
                            disabled={!tableRows.length}
                            onClick={handleNormalize}
                        >
                            Normalize
                        </Button>
                    )}

                    <Button
                        variant="outlined"
                        disabled={!tableRows.length}
                        onClick={handleCancel}
                    >
                        Cancel
                    </Button>

                    <Button
                        variant="contained"
                        disabled={!tableRows.length}
                        onClick={handleSave}
                    >
                        Save Changes
                    </Button>
                </Box>
            </Box>

            {!tableRows.length ? (
                <Paper sx={{ mt: 3, p: 4, textAlign: "center" }}>
                    No table data available. Please select filters and apply.
                </Paper>
            ) : (
                <TableContainer
                    sx={{
                        overflowX: "auto",
                        border: "1px solid #D8DEE8",
                        borderRadius: "12px",
                    }}
                >
                    <Table size="small" sx={{ minWidth: "max-content" }}>
                        <TableHead>
                            <TableRow>
                                <TableCell
                                    sx={{ fontWeight: 700, minWidth: 150, position: "sticky", left: 0, zIndex: 3, backgroundColor: "#fff" }}>
                                    Product / LOT
                                </TableCell>

                                {allMonths.map((month, index) => (
                                    <TableCell key={`${month}-${index}`} align="center">
                                        {month}
                                    </TableCell>
                                ))}
                            </TableRow>
                        </TableHead>

                        <TableBody>
                            {metric === "market_share" ? (
                                tableRows.map((lotGroup, lotIndex) => (
                                    <React.Fragment key={lotGroup.lot}>
                                        <TableRow
                                            onClick={() => toggleLot(lotGroup.lot)}
                                            sx={{
                                                cursor: "pointer",
                                                backgroundColor: "#f8fafc",
                                            }}
                                        >
                                            <TableCell
                                                sx={{ fontWeight: 700, position: "sticky", left: 0, zIndex: 2, backgroundColor: "#f8fafc" }}>
                                                {expandedLots[lotGroup.lot] ? "▼" : "▶"} {lotGroup.lot}
                                            </TableCell>

                                            {(lotGroup.total || []).map((value, i) => (
                                                <TableCell key={i} align="center" sx={{ fontWeight: 700 }}>
                                                    {value}
                                                </TableCell>
                                            ))}
                                        </TableRow>

                                        {expandedLots[lotGroup.lot] &&
                                            lotGroup.children.map((row, childIndex) => (
                                                <TableRow key={`${lotGroup.lot}-${row.label}`}>
                                                    <TableCell
                                                        sx={{ pl: 4, position: "sticky", left: 0, zIndex: 1, backgroundColor: "#fff", }}>
                                                        {row.label}
                                                    </TableCell>

                                                    {row.values.map((value, index) => (
                                                        <TableCell
                                                            key={index}
                                                            align="center"
                                                            sx={{
                                                                color:
                                                                    row.label?.toLowerCase() ===
                                                                        selectedProduct?.toLowerCase() &&
                                                                        index >= forecastStartIndex
                                                                        ? "#f59e0b"
                                                                        : "#334155",
                                                                fontWeight:
                                                                    row.label?.toLowerCase() ===
                                                                        selectedProduct?.toLowerCase() &&
                                                                        index >= forecastStartIndex
                                                                        ? 700
                                                                        : 400,
                                                                backgroundColor:
                                                                    row.label?.toLowerCase() ===
                                                                        selectedProduct?.toLowerCase() &&
                                                                        index >= forecastStartIndex
                                                                        ? "#fffdf5"
                                                                        : "white",
                                                            }}
                                                        >
                                                            {editable ? (
                                                                <input
                                                                    value={value}
                                                                    onChange={(e) =>
                                                                        handleCellChange(
                                                                            lotIndex,
                                                                            childIndex,
                                                                            index,
                                                                            e.target.value
                                                                        )
                                                                    }
                                                                    style={{
                                                                        width: "70px",
                                                                        height: "28px",
                                                                        border: "1px solid #CBD5E1",
                                                                        borderRadius: "4px",
                                                                        padding: "4px 6px",
                                                                        textAlign: "center",
                                                                    }}
                                                                />
                                                            ) : (
                                                                value
                                                            )}
                                                        </TableCell>
                                                    ))}
                                                </TableRow>
                                            ))}
                                    </React.Fragment>
                                ))
                            ) : (
                                tableRows.map((row, rowIndex) => {
                                    const child = row.children?.[0];

                                    return (
                                        <TableRow key={`${row.lot}-${rowIndex}`}>
                                            <TableCell
                                                sx={{ fontWeight: 700, position: "sticky", left: 0, zIndex: 1, backgroundColor: "#fff" }}>
                                                {row.lot}
                                            </TableCell>

                                            {(child?.values || []).map((value, index) => (
                                                <TableCell
                                                    key={index}
                                                    align="center"
                                                    sx={{
                                                        color:
                                                            row.lot?.toLowerCase() ===
                                                                selectedLot?.toLowerCase() &&
                                                                index >= forecastStartIndex
                                                                ? "#f59e0b"
                                                                : "#334155",
                                                    }}
                                                >
                                                    {editable ? (
                                                        <input
                                                            value={value}
                                                            onChange={(e) =>
                                                                handleCellChange(
                                                                    rowIndex,
                                                                    0,
                                                                    index,
                                                                    e.target.value
                                                                )
                                                            }
                                                            style={{
                                                                width: "70px",
                                                                height: "28px",
                                                                border: "1px solid #CBD5E1",
                                                                borderRadius: "4px",
                                                                padding: "4px 6px",
                                                                textAlign: "center",
                                                            }}
                                                        />
                                                    ) : (
                                                        value
                                                    )}
                                                </TableCell>
                                            ))}
                                        </TableRow>
                                    );
                                })
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            )}
        </>
    );
}