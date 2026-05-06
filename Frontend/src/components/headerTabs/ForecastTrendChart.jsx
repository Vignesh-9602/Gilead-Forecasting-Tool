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
    Box, TextField
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import Plot from "react-plotly.js";
import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import { saveChanges } from "../../services/apiService";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";

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
    updateTableData,
    updateAllMetricsData,
    onUpdateScenario,
    onSaveScenario,
    scenarioSelector
}) {
    const allMonths =
        chartData?.months?.map((month) =>
            new Date(month).toLocaleDateString("en-US", {
                month: "short",
                year: "2-digit",
            })
        ) || [];

    // const trainValues = chartData?.train_values || [];
    // const forecastValues = chartData?.forecast_values || [];
    // const forecastStartIndex = chartData?.forecast_start_index || 0;

    const [editable, setEditable] = useState(false);
    const [tableRows, setTableRows] = useState([]);
    const [originalRows, setOriginalRows] = useState([]);
    const [expandedLots, setExpandedLots] = useState({});
    const [lastEditedCell, setLastEditedCell] = useState(null);
    const [openDialog, setOpenDialog] = useState(false);
    const [scenarioName, setScenarioName] = useState("");

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

        // Clear chart instantly
        if (typeof updateChartData === "function") {
            updateChartData(null);
        }

        // Optional: also clear this metric from parent state
        if (typeof updateAllMetricsData === "function") {
            updateAllMetricsData(prev => ({
                ...prev,
                [metric]: {
                    chart: null,
                    table: []
                }
            }));
        }
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
        // if (typeof updateTableData === "function") {
        //     updateTableData(updatedRows);
        // }

        // if (typeof updateAllMetricsData === "function") {
        //     updateAllMetricsData(prev => ({
        //         ...prev,
        //         [metric]: {
        //             ...prev[metric],
        //             table: updatedRows
        //         }
        //     }));
        // }
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

    // const trainX = allMonths.slice(0, forecastStartIndex);
    // const trainY = trainValues;

    // const forecastX = [
    //     allMonths[forecastStartIndex - 1],
    //     ...allMonths.slice(forecastStartIndex),
    // ];

    // const forecastY = [
    //     trainValues[trainValues.length - 1],
    //     ...forecastValues,
    // ];

    const forecastStartIndex = chartData?.forecast_start_index || 0;
    const series = chartData?.series || [];

    const traces = series.flatMap((item) => {
        const trainX = allMonths.slice(0, forecastStartIndex);

        const forecastX = [
            allMonths[forecastStartIndex - 1],
            ...allMonths.slice(forecastStartIndex),
        ];

        const isNps = metric === "nps";

        const isSelectedLot =
            item.lot?.toLowerCase() === selectedLot?.toLowerCase();

        const isSelectedProduct =
            item.label?.toLowerCase() === selectedProduct?.toLowerCase();

        let color = "#d1d5db";
        let width = 2;

        if (isNps) {
            if (isSelectedLot) {
                color = "#f59e0b";
                width = 3;
            }
        } else {
            if (isSelectedProduct) {
                color = "#f59e0b";
                width = 3;
            }
        }

        return [
            {
                x: trainX,
                y: item.train_values,
                type: "scatter",
                mode: "lines",
                name: `${item.lot} ${item.label}`,
                line: {
                    color,
                    width,
                },
            },
            {
                x: forecastX,
                y: [
                    item.train_values[item.train_values.length - 1],
                    ...item.forecast_values,
                ],
                type: "scatter",
                mode: "lines",
                showlegend: false,
                line: {
                    color,
                    width,
                    dash: "dot",
                },
            },
        ];
    });

    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "160px",
        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
        },
    };

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

    const handleRefresh = async () => {
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

            const updatedMetricData = data?.metrics_data?.[metric];

            if (updatedMetricData) {
                // update table after backend recalculation
                setTableRows(updatedMetricData.table || []);
                setOriginalRows(updatedMetricData.table || []);

                // update chart
                if (typeof updateChartData === "function") {
                    updateChartData(updatedMetricData.chart || null);
                }

                // update parent metrics_data
                if (typeof updateAllMetricsData === "function") {
                    updateAllMetricsData(prev => ({
                        ...prev,
                        [metric]: {
                            chart: updatedMetricData.chart || null,
                            table: updatedMetricData.table || []
                        }
                    }));
                }
            }

            setEditable(false);
        } catch (error) {
            console.error("Save Changes API failed:", error);
        }
    };

    const renderEditableCell = (
        value,
        lotIndex,
        childIndex,
        index,
        highlight = false
    ) => {
        return editable ? (
            <input
                value={value}
                onChange={(e) => {
                    const input = e.target.value;
                    if (/^\d*\.?\d*$/.test(input)) {
                        handleCellChange(lotIndex, childIndex, index, input);
                    }
                }}
                style={{
                    // width: "42px",
                    width: "100%",
                    maxWidth: "38px",
                    border: "none",
                    outline: "none",
                    background: "transparent",
                    textAlign: "center",
                    fontSize: "14px",
                    padding: 0,
                }}
            />
        ) : (
            <Box
                sx={{
                    color: highlight ? "#f59e0b" : "#334155",
                    fontWeight: highlight ? 700 : 400,
                }}
            >
                {value}
            </Box>
        );
    };

    const allValues = series.flatMap(item => [
        ...item.train_values,
        ...item.forecast_values
    ]);

    const maxValue = Math.max(...allValues);

    // Option 1: simple buffer
    const yMax = maxValue + 800;

    // Option 2: round to next 100
    const yMaxRounded = Math.ceil(maxValue / 1000) * 1000;

    // Option 3: round to next 1000
    const yMax1000 = Math.ceil(maxValue / 1500) * 1500;

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
                                    xaxis: {
                                        tickangle: -45,
                                        showgrid: true,
                                    },
                                    yaxis: {
                                        showgrid: true,
                                        range: [0, yMax],
                                        // dtick: 50,
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
                    <Button
                        variant="contained"
                        sx={{ height: "35px", borderRadius: "10px", textTransform: "none" }}
                        onClick={() => setOpenDialog(true)}
                        disabled={!tableRows.length}
                    // disabled={scenarioSelector !== "BASE"}
                    >
                        Save Scenario
                    </Button>
                </Box>

                {/* RIGHT SIDE BUTTONS */}
                <Box sx={{ display: "flex", gap: 2 }}>
                    <Button
                        variant="contained"
                        sx={{ height: "35px", borderRadius: "10px", textTransform: "none" }}
                        disabled={editable || !tableData.length || !tableRows.length}
                        onClick={() => {
                            if (scenarioSelector?.toUpperCase() === "BASE") {
                                setOpenDialog(true);   // open save modal
                            } else {
                                onUpdateScenario();    // normal update
                            }
                        }}
                    >
                        Save
                    </Button>
                    <Button
                        variant="outlined"
                        sx={{ height: "35px", borderRadius: "10px", textTransform: "none" }}
                        disabled={!tableRows.length}
                        onClick={() => setEditable(true)}
                    >
                        Edit Changes
                    </Button>

                    {editable && (
                        <Button
                            variant="contained"
                            sx={{ height: "35px", borderRadius: "10px", textTransform: "none" }}
                            disabled={!tableRows.length}
                            onClick={handleRefresh}
                        >
                            Refresh
                        </Button>
                    )}

                    {metric === "market_share" && editable && (
                        <Button
                            variant="outlined"
                            sx={{ height: "35px", borderRadius: "10px", textTransform: "none" }}
                            disabled={!tableRows.length}
                            onClick={handleNormalize}
                        >
                            Normalize
                        </Button>
                    )}

                    <Button
                        variant="outlined"
                        sx={{ height: "35px", borderRadius: "10px", textTransform: "none" }}
                        disabled={!tableRows.length}
                        onClick={handleCancel}
                    >
                        Cancel
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
                                    sx={{ fontWeight: 700, minWidth: 150, position: "sticky", left: 0, zIndex: 3, backgroundColor: "#fff", borderRight: "1px solid #E2E8F0", }}>
                                    Product / LOT
                                </TableCell>

                                {allMonths.map((month, index) => (
                                    <TableCell key={`${month}-${index}`} align="center" sx={{
                                        borderRight: "1px solid #E2E8F0",
                                    }}>
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
                                                <TableCell key={i} align="center" sx={{ fontWeight: 700, borderRight: "1px solid #E2E8F0", }}>
                                                    {value}
                                                </TableCell>
                                            ))}
                                        </TableRow>

                                        {expandedLots[lotGroup.lot] &&
                                            lotGroup.children.map((row, childIndex) => (
                                                <TableRow key={`${lotGroup.lot}-${row.label}`}>
                                                    <TableCell
                                                        sx={{
                                                            pl: 4, position: "sticky", left: 0, zIndex: 1, backgroundColor: "#fff", borderRight: "1px solid #E2E8F0",
                                                            backgroundColor:
                                                                row.label?.toLowerCase() === selectedProduct?.toLowerCase() &&
                                                                    lotGroup.lot?.toLowerCase() === selectedLot?.toLowerCase()
                                                                    ? "#fffbeb"
                                                                    : "#fff",

                                                            color:
                                                                row.label?.toLowerCase() === selectedProduct?.toLowerCase() &&
                                                                    lotGroup.lot?.toLowerCase() === selectedLot?.toLowerCase()
                                                                    ? "#f59e0b"
                                                                    : "#334155",

                                                            fontWeight:
                                                                row.label?.toLowerCase() === selectedProduct?.toLowerCase() &&
                                                                    lotGroup.lot?.toLowerCase() === selectedLot?.toLowerCase()
                                                                    ? 700
                                                                    : 400,
                                                        }}>
                                                        {row.label}
                                                    </TableCell>

                                                    {row.values.map((value, index) => (
                                                        <TableCell
                                                            key={index}
                                                            align="center"
                                                            sx={{
                                                                borderRight: "1px solid #E2E8F0",

                                                                backgroundColor:
                                                                    index < forecastStartIndex
                                                                        ? "#f1f5f9"
                                                                        : row.label?.toLowerCase() === selectedProduct?.toLowerCase() &&
                                                                            lotGroup.lot?.toLowerCase() === selectedLot?.toLowerCase()
                                                                            ? "#fffbeb"
                                                                            : "#fff",

                                                                color:
                                                                    index >= forecastStartIndex &&
                                                                        row.label?.toLowerCase() === selectedProduct?.toLowerCase() &&
                                                                        lotGroup.lot?.toLowerCase() === selectedLot?.toLowerCase()
                                                                        ? "#f59e0b"
                                                                        : "#334155",

                                                                fontWeight:
                                                                    index >= forecastStartIndex &&
                                                                        row.label?.toLowerCase() === selectedProduct?.toLowerCase() &&
                                                                        lotGroup.lot?.toLowerCase() === selectedLot?.toLowerCase()
                                                                        ? 700
                                                                        : 400,
                                                            }}
                                                        >
                                                            {renderEditableCell(
                                                                value,
                                                                lotIndex,
                                                                childIndex,
                                                                index,
                                                                index >= forecastStartIndex &&
                                                                row.label?.toLowerCase() === selectedProduct?.toLowerCase() &&
                                                                lotGroup.lot?.toLowerCase() === selectedLot?.toLowerCase()
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
                                                sx={{
                                                    fontWeight: 700, position: "sticky", left: 0, zIndex: 1, backgroundColor: "#fff",
                                                    backgroundColor:
                                                        row.lot?.toLowerCase() === selectedLot?.toLowerCase()
                                                            ? "#fffbeb"
                                                            : "#fff",

                                                    color:
                                                        row.lot?.toLowerCase() === selectedLot?.toLowerCase()
                                                            ? "#f59e0b"
                                                            : "#334155",
                                                }}>
                                                {row.lot}
                                            </TableCell>

                                            {(child?.values || []).map((value, index) => (
                                                <TableCell
                                                    key={index}
                                                    align="center"
                                                    sx={{
                                                        borderRight: "1px solid #E2E8F0",

                                                        backgroundColor:
                                                            index < forecastStartIndex
                                                                ? "#f1f5f9"
                                                                : row.lot?.toLowerCase() === selectedLot?.toLowerCase()
                                                                    ? "#fffbeb"
                                                                    : "#fff",

                                                        color:
                                                            index >= forecastStartIndex &&
                                                                row.lot?.toLowerCase() === selectedLot?.toLowerCase()
                                                                ? "#f59e0b"
                                                                : "#334155",

                                                        fontWeight:
                                                            index >= forecastStartIndex &&
                                                                row.lot?.toLowerCase() === selectedLot?.toLowerCase()
                                                                ? 700
                                                                : 400,
                                                    }}
                                                >
                                                    {renderEditableCell(
                                                        value,
                                                        rowIndex,
                                                        0,
                                                        index,
                                                        row.lot?.toLowerCase() === selectedLot?.toLowerCase() &&
                                                        index >= forecastStartIndex
                                                    )}
                                                </TableCell>
                                            ))}
                                        </TableRow>
                                    );
                                })
                            )}
                        </TableBody>
                    </Table>
                </TableContainer >
            )
            }
            <Dialog open={openDialog} onClose={() => setOpenDialog(false)}>
                <DialogTitle>Save Scenario</DialogTitle>

                <DialogContent>
                    <TextField
                        autoFocus
                        fullWidth
                        label="Scenario Name"
                        placeholder="e.g. Adjusted Baseline"
                        value={scenarioName}
                        onChange={(e) => setScenarioName(e.target.value)}
                        sx={{ mt: 1 }}
                    />
                </DialogContent>

                <DialogActions>
                    <Button onClick={() => setOpenDialog(false)}>
                        Cancel
                    </Button>

                    <Button
                        variant="contained"
                        onClick={() => {
                            onSaveScenario(scenarioName);
                            setOpenDialog(false);
                            setScenarioName("");
                        }}
                    >
                        Save
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
}