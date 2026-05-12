import React, { useState, useEffect } from "react";
import {
    Box,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    IconButton,
    Tooltip,
    Typography,
    Button,
    Radio,
    FormControl,
    Select,
    MenuItem,
} from "@mui/material";

import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";

export default function ScenarioTable({
    chartData,
    tableData,
    selectedLot,
    tableMetric,
    setTableMetric,
    onSaveSelection
}) {
    const allMonths =
        chartData?.months?.map((month) =>
            new Date(month).toLocaleDateString("en-US", {
                month: "short",
                year: "2-digit",
            })
        ) || [];


    const forecastStartIndex =
        chartData?.forecast_start_index || 0;

    const [expandedRows, setExpandedRows] = useState({});
    const [selectedScenario, setSelectedScenario] = useState("");
    const formatValue = (value) => {
        if (value === null || value === undefined) return "-";

        if (tableMetric === "market_share") {
            return `${Number(value).toFixed(2)}%`;
        }

        return Number(value).toFixed(0);
    };
    useEffect(() => {
        const initial = {};
        (tableData || []).forEach((row) => {
            initial[row.scenario] = false;
        });
        setExpandedRows(initial);
    }, [tableData]);

    const toggleRow = (scenario) => {
        setExpandedRows((prev) => ({
            ...prev,
            [scenario]: !prev[scenario],
        }));
    };

    const handleExpandAll = () => {
        const all = {};
        (tableData || []).forEach((row) => {
            all[row.scenario] = true;
        });
        setExpandedRows(all);
    };

    const handleCollapseAll = () => {
        const all = {};
        (tableData || []).forEach((row) => {
            all[row.scenario] = false;
        });
        setExpandedRows(all);
    };

    const handleSaveSelection = () => {
        if (!selectedScenario) return;
        onSaveSelection(selectedScenario);
    };

    return (
        <>
            <Box
                sx={{
                    mt: 3,
                    mb: 1,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                }}
            >
                <Typography sx={{ fontWeight: 700 }}>
                    COMPARISON MATRIX
                </Typography>


                {tableData?.length > 0 && (
                    <Box sx={{ display: "flex", gap: 1 }}>
                        <FormControl size="small" sx={{ minWidth: 180 }}>
                            <Select
                                value={tableMetric}
                                onChange={(e) => setTableMetric(e.target.value)}
                            >
                                <MenuItem value="nps">Overall Market Volume</MenuItem>
                                <MenuItem value="market_share">
                                    Market Share
                                </MenuItem>
                            </Select>
                        </FormControl>
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

                        <Button
                            variant="contained"
                            onClick={handleSaveSelection}
                            disabled={!selectedScenario}
                            sx={{
                                textTransform: "none",
                                borderRadius: "8px",
                                backgroundColor: "#1e293b",
                                // disabled: "!tableData"
                            }}
                        >
                            Save Selection for {selectedLot || "LOT"}
                        </Button>
                    </Box>
                )}
            </Box>

            {!tableData?.length ? (
                <Box
                    sx={{
                        mt: 3,
                        p: 4,
                        textAlign: "center",
                        color: "#94a3b8",
                        fontWeight: 500,
                        border: "1px solid #D8DEE8",
                        borderRadius: "12px",
                    }}
                >
                    No table data available. Please select filters and apply.
                </Box>
            ) : (
                <TableContainer
                    sx={{
                        border: "1px solid #D8DEE8",
                        borderRadius: "12px",
                        overflowX: "auto",
                        maxHeight: 500,
                    }}
                >
                    <Table size="small" sx={{ minWidth: "max-content" }}>
                        <TableHead>
                            <TableRow>
                                <TableCell
                                    sx={{
                                        fontWeight: 700,
                                        position: "sticky",
                                        left: 0,
                                        zIndex: 5,
                                        backgroundColor: "#fff",
                                        minWidth: 70,
                                        borderRight: "1px solid #E2E8F0",
                                    }}
                                >
                                    Select
                                </TableCell>

                                <TableCell
                                    sx={{
                                        fontWeight: 700,
                                        position: "sticky",
                                        left: 70,
                                        zIndex: 5,
                                        backgroundColor: "#fff",
                                        minWidth: 180,
                                        borderRight: "1px solid #E2E8F0",
                                    }}
                                >
                                    Scenario
                                </TableCell>

                                {allMonths.map((month, index) => (
                                    <TableCell key={index} align="center"
                                        sx={{
                                            borderRight: "1px solid #E2E8F0",
                                        }}>
                                        {month}
                                    </TableCell>
                                ))}
                            </TableRow>
                        </TableHead>

                        <TableBody>
                            {tableData.map((scenarioRow) => {
                                const isSelected =
                                    selectedScenario === scenarioRow.scenario;

                                return (
                                    <React.Fragment key={scenarioRow.scenario}>
                                        <TableRow
                                            sx={{
                                                backgroundColor: isSelected
                                                    ? "#dbeafe"
                                                    : "#f8fafc",
                                            }}
                                        >
                                            <TableCell
                                                sx={{
                                                    position: "sticky",
                                                    left: 0,
                                                    backgroundColor: isSelected
                                                        ? "#dbeafe"
                                                        : "#f8fafc",
                                                    zIndex: 4,
                                                    borderRight: "1px solid #E2E8F0",
                                                }}
                                            >
                                                <Radio
                                                    checked={isSelected}
                                                    onChange={() =>
                                                        setSelectedScenario(
                                                            scenarioRow.scenario
                                                        )
                                                    }
                                                />
                                            </TableCell>

                                            <TableCell
                                                onClick={() =>
                                                    toggleRow(scenarioRow.scenario)
                                                }
                                                sx={{
                                                    fontWeight: 700,
                                                    cursor: "pointer",
                                                    position: "sticky",
                                                    left: 70,
                                                    backgroundColor: isSelected
                                                        ? "#dbeafe"
                                                        : "#f8fafc",
                                                    zIndex: 4,
                                                    borderRight: "1px solid #E2E8F0",
                                                }}
                                            >
                                                {expandedRows[scenarioRow.scenario]
                                                    ? "▼"
                                                    : "▶"}{" "}
                                                {scenarioRow.scenario}
                                            </TableCell>

                                            {scenarioRow.total.map((value, index) => (
                                                <TableCell key={index} align="center"
                                                    sx={{
                                                        backgroundColor:
                                                            index < forecastStartIndex
                                                                ? "#f1f5f9"
                                                                : "#fff",
                                                        borderRight: "1px solid #E2E8F0",
                                                    }}>
                                                    {value}
                                                </TableCell>
                                            ))}
                                        </TableRow>

                                        {expandedRows[scenarioRow.scenario] &&
                                            scenarioRow.children.map((child) => (
                                                <TableRow key={child.label}>
                                                    <TableCell
                                                        sx={{
                                                            position: "sticky",
                                                            left: 0,
                                                            backgroundColor: "#fff",
                                                            zIndex: 3,
                                                            borderRight: "1px solid #E2E8F0",
                                                        }}
                                                    />

                                                    <TableCell
                                                        sx={{
                                                            pl: 4,
                                                            position: "sticky",
                                                            left: 70,
                                                            backgroundColor: "#fff",
                                                            zIndex: 3,
                                                            borderRight: "1px solid #E2E8F0",
                                                        }}
                                                    >
                                                        {child.label}
                                                    </TableCell>

                                                    {child.values.map((value, index) => (
                                                        <TableCell key={index} align="center" sx={{
                                                            backgroundColor:
                                                                index < forecastStartIndex
                                                                    ? "#f1f5f9"
                                                                    : "#fff",
                                                            borderRight: "1px solid #E2E8F0",
                                                        }}>
                                                            {value}
                                                        </TableCell>
                                                    ))}
                                                </TableRow>
                                            ))}
                                    </React.Fragment>
                                );
                            })}
                        </TableBody>
                    </Table>
                </TableContainer>
            )}
        </>
    );
}