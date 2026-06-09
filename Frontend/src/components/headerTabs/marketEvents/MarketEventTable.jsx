import React, {
    useMemo,
    useState,
    useEffect,
} from "react";

import {
    Box,
    Button,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    FormControl,
    Select,
    MenuItem,
} from "@mui/material";

import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import { saveMarketEventTable } from "../../../services/apiService";
import { useLoadingStore } from "../../../stores";
import DownloadIcon from "@mui/icons-material/Download";
import ExcelJS from "exceljs";
import { saveAs } from "file-saver";

export default function MarketEventTable({
    metricsData,
    months,
    therapyArea,
    indication,
    selectedScenario,
    setMarketShareChartData,
    setMarketEventMetricsData,
    showSnackbar,
    startDate,
    endDate,
}) {

    const [editable, setEditable] = useState(false);
    const [selectedMetricView, setSelectedMetricView] = useState("nps");
    const [editedCell, setEditedCell] = useState(null);
    const { setLoading, isLoading } = useLoadingStore();

    const formattedMonths = useMemo(() => {
        return (
            months?.map((month) =>
                new Date(month).toLocaleDateString(
                    "en-US",
                    {
                        month: "short",
                        year: "2-digit",
                    }
                )
            ) || []
        );

    }, [months]);

    // dynamic table source
    const tableRows = useMemo(() => {

        if (!metricsData) return [];

        return (
            metricsData?.[selectedMetricView]
                ?.table || []
        );

    }, [metricsData, selectedMetricView]);

    const forecastStartIndex =
        metricsData?.[selectedMetricView]
            ?.chart?.forecast_start_index || 0;

    const [editableRows, setEditableRows] = useState([]);

    const [originalRows, setOriginalRows] = useState([]);

    useEffect(() => {
        const cloned =
            JSON.parse(
                JSON.stringify(tableRows)
            );

        setEditableRows(cloned);
        setOriginalRows(cloned);

    }, [tableRows]);

    const [expandedLots, setExpandedLots] =
        useState({});

    useEffect(() => {
        const expanded = {};
        tableRows.forEach((row) => {
            expanded[row.lot] = true;
        });
        setExpandedLots(expanded);

    }, [tableRows]);

    const hasTableData = editableRows.length > 0;

    const handleCellChange = (
        lotIndex,
        childIndex,
        valueIndex,
        value
    ) => {

        const updatedRows =
            JSON.parse(
                JSON.stringify(editableRows)
            );

        updatedRows[lotIndex]
            .children[childIndex]
            .values[valueIndex] = value;

        setEditableRows(updatedRows);
    };

    const handleCancel = () => {

        setEditableRows(
            JSON.parse(
                JSON.stringify(originalRows)
            )
        );

        setEditable(false);
    };

    const handleExpandAll = () => {

        const expanded = {};

        editableRows.forEach((row) => {
            expanded[row.lot] = true;
        });

        setExpandedLots(expanded);
    };

    const handleCollapseAll = () => {

        const collapsed = {};

        editableRows.forEach((row) => {
            collapsed[row.lot] = false;
        });

        setExpandedLots(collapsed);
    };

    const toggleLot = (lot) => {

        setExpandedLots((prev) => ({
            ...prev,
            [lot]: !prev[lot],
        }));
    };

    const formatValue = (value) => {
        if (value === null || value === undefined) return "-";

        if (selectedMetricView === "market_share") {
            return `${parseFloat(value)}%`;
        }

        return Number(value);
    };

    const renderEditableCell = (
        value,
        lotIndex,
        childIndex,
        valueIndex
    ) => {

        return editable ? (

            <input
                value={value}

                onChange={(e) => {

                    const input =
                        e.target.value;

                    if (
                        /^\d*\.?\d*$/.test(input)
                    ) {

                        handleCellChange(
                            lotIndex,
                            childIndex,
                            valueIndex,
                            input
                        );
                        setEditedCell({
                            lotIndex,
                            childIndex,
                            valueIndex,
                        })
                    }
                }}
                style={{
                    width: "48px",
                    height: "24px",
                    boxSizing: "border-box",
                    display: "inline-block",
                    border: "1px solid #93c5fd",
                    borderRadius: "4px",
                    outline: "none",
                    background: "#eff6ff",
                    color: "#1e293b",
                    textAlign: "center",
                    fontSize: "13px",
                    lineHeight: "20px",
                    padding: "1px 4px",
                }}
            />

        ) : (

            <Box
                sx={{
                    color: "#334155",
                    fontSize: "13px",
                    minHeight: "24px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                }}
            >
                {formatValue(value)}
            </Box>
        );
    };

    const handleNormalize = () => {

        if (!editedCell) return;

        const updatedRows =
            JSON.parse(JSON.stringify(editableRows));

        const {
            lotIndex,
            childIndex,
            valueIndex,
        } = editedCell;

        const lotGroup =
            updatedRows[lotIndex];

        const targetTotal =
            Number(
                lotGroup.total[valueIndex]
            );

        const editedValue =
            Number(
                lotGroup.children[
                    childIndex
                ].values[valueIndex]
            );

        const remainingChildren =
            lotGroup.children.filter(
                (_, idx) => idx !== childIndex
            );

        const remainingCurrentTotal =
            remainingChildren.reduce(
                (sum, child) =>
                    sum +
                    Number(
                        child.values[valueIndex] || 0
                    ),
                0
            );

        const remainingTarget =
            targetTotal - editedValue;

        if (
            remainingCurrentTotal <= 0
        ) {
            return;
        }

        const ratio =
            remainingTarget /
            remainingCurrentTotal;

        remainingChildren.forEach(
            (child) => {

                const current =
                    Number(
                        child.values[valueIndex] || 0
                    );

                const normalizedValue =
                    current * ratio;

                if (selectedMetricView === "nps") {

                    child.values[valueIndex] =
                        Math.round(normalizedValue);

                } else {

                    child.values[valueIndex] =
                        Number(
                            normalizedValue.toFixed(2)
                        );
                }
            }
        );

        setEditableRows(updatedRows);
    };

    const handleSave = async () => {

        try {
            setLoading(true);
            const payload = {
                ta_name: therapyArea,

                indication,

                scenario_name: selectedScenario,

                metric: selectedMetricView,
                start_date: startDate,
                end_date: endDate,

                table: editableRows.map((row) => ({
                    lot: row.lot,

                    total: row.total.map((value) =>
                        Number(value)
                    ),

                    children: row.children.map(
                        (child) => ({
                            label: child.label,

                            values: child.values.map(
                                (value) =>
                                    Number(value)
                            ),
                        })
                    ),
                })),
            };

            console.log(
                "SAVE MARKET EVENT TABLE PAYLOAD"
            );

            console.log(payload);

            const response =
                await saveMarketEventTable(
                    payload
                );

            const data = response?.data;

            console.log(
                "SAVE RESPONSE",
                data
            );

            // update chart
            setMarketShareChartData(
                data?.metrics_data
                    ?.market_share?.chart || null
            );

            // update table
            setMarketEventMetricsData(
                data?.metrics_data || null
            );

            // exit edit mode
            setEditable(false);

            setOriginalRows(
                JSON.parse(JSON.stringify(editableRows))
            );

            showSnackbar("Market event saved successfully", "success");

        } catch (error) {
            console.error("Failed to save market event table", error);
            showSnackbar("Failet to save market event", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleDownloadExcel = async () => {
        if (!editableRows.length) return;

        const workbook = new ExcelJS.Workbook();
        const worksheet = workbook.addWorksheet("Market Event");

        worksheet.addRow(["Indication", indication]);
        worksheet.addRow(["Scenario", selectedScenario]);
        worksheet.addRow([
            "Metric",
            selectedMetricView === "market_share"
                ? "Market Share"
                : "Overall Market Volume"
        ]);
        worksheet.addRow([
            "Start Date",
            new Date(startDate).toLocaleDateString("en-US", {
                month: "short",
                year: "2-digit",
            })
        ]);
        worksheet.addRow([
            "End Date",
            new Date(endDate).toLocaleDateString("en-US", {
                month: "short",
                year: "2-digit",
            })
        ]);

        worksheet.addRow([]);

        const headerRowNumber = worksheet.rowCount + 1;

        worksheet.addRow([
            "Product / LOT",
            ...formattedMonths
        ]);

        editableRows.forEach((lotGroup) => {
            const lotRow = worksheet.addRow([
                lotGroup.lot,
                ...(lotGroup.total || [])
            ]);

            lotRow.font = { bold: true };

            lotGroup.children.forEach((child) => {
                worksheet.addRow([
                    child.label,
                    ...(child.values || [])
                ]);
            });
        });

        worksheet.eachRow((row) => {
            row.eachCell((cell) => {
                cell.alignment = {
                    horizontal: "center",
                    vertical: "middle"
                };

                cell.border = {
                    top: { style: "thin" },
                    left: { style: "thin" },
                    bottom: { style: "thin" },
                    right: { style: "thin" }
                };
            });
        });

        worksheet.getRow(headerRowNumber).font = {
            bold: true
        };

        worksheet.getColumn(1).width = 25;

        for (let i = 2; i <= formattedMonths.length + 1; i++) {
            worksheet.getColumn(i).width = 12;
        }

        const buffer = await workbook.xlsx.writeBuffer();

        saveAs(
            new Blob([buffer]),
            `Market_Event_${selectedScenario}_${indication}.xlsx`
        );
    };

    return (
        <Paper
            sx={{
                mt: 3,
                p: 2,
                borderRadius: "16px",
                border: "1px solid #D8DEE8",
                boxShadow: "none",
            }}
        >

            {/* TOP ACTIONS */}
            <Box
                sx={{
                    mb: 2,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 2,
                }}
            >

                {/* LEFT */}
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                    }}
                >
                    <Tooltip title="Expand All">
                        <IconButton
                            onClick={handleExpandAll}
                            disabled={!hasTableData}
                        >
                            <UnfoldMoreIcon />
                        </IconButton>
                    </Tooltip>

                    <Tooltip title="Collapse All">
                        <IconButton
                            onClick={handleCollapseAll}
                            disabled={!hasTableData}
                        >
                            <UnfoldLessIcon />
                        </IconButton>
                    </Tooltip>
                </Box>

                {/* RIGHT */}
                <Box
                    sx={{
                        display: "flex",
                        gap: 1.5,
                        alignItems: "center",
                        flexWrap: "wrap",
                    }}
                >
                    <Tooltip title="Download Table">
                        <IconButton
                            onClick={handleDownloadExcel}
                            disabled={!hasTableData}
                        >
                            <DownloadIcon />
                        </IconButton>
                    </Tooltip>
                    {/* METRIC SELECT */}
                    <FormControl
                        size="small"
                        sx={{
                            minWidth: 220,

                            "& .MuiOutlinedInput-root": {
                                height: "35px",
                                borderRadius: "10px",
                                backgroundColor: "#fff",
                            },
                        }}
                        disabled={!hasTableData}
                    >
                        <Select
                            value={selectedMetricView}
                            onChange={(e) =>
                                setSelectedMetricView(
                                    e.target.value
                                )
                            }
                        >
                            <MenuItem value="nps">
                                Overall Market Volume
                            </MenuItem>

                            <MenuItem value="market_share">
                                Market Share
                            </MenuItem>
                        </Select>
                    </FormControl>

                    <Button
                        variant="contained"
                        onClick={handleSave}
                        sx={{
                            height: "35px",
                            borderRadius: "10px",
                            textTransform: "none",
                        }}
                        disabled={!hasTableData || !editable}
                    >
                        Save
                    </Button>

                    <Button
                        variant="outlined"
                        onClick={() =>
                            setEditable(true)
                        }
                        sx={{
                            height: "35px",
                            borderRadius: "10px",
                            textTransform: "none",
                        }}
                        disabled={!hasTableData}
                    >
                        {editable ? "Editing..." : "Edit Changes"}
                    </Button>

                    {editable && (
                        <Button
                            variant="outlined"
                            sx={{
                                height: "35px",
                                borderRadius: "10px",
                                textTransform: "none",
                            }}
                            disabled={!hasTableData}
                            onClick={handleNormalize}
                        >
                            Normalize
                        </Button>
                    )}

                    <Button
                        variant="outlined"
                        // color="error"
                        onClick={handleCancel}
                        sx={{
                            height: "35px",
                            borderRadius: "10px",
                            textTransform: "none",
                        }}
                        disabled={!hasTableData}
                    >
                        Cancel
                    </Button>
                </Box>
            </Box>

            {/* TABLE */}
            {editableRows.length === 0 ? (
                <Box
                    sx={{
                        height: 120,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "#94a3b8",
                        fontSize: "14px",
                        border: "1px solid #D8DEE8",
                        borderRadius: "12px",
                    }}
                >
                    No table data available. Please apply filters.
                </Box>

            ) : (
                <TableContainer
                    sx={{
                        overflowX: "auto",
                        border: "1px solid #D8DEE8",
                        borderRadius: "12px",
                    }}
                >
                    <Table
                        size="small"
                        sx={{
                            minWidth: "max-content",
                        }}
                    >

                        {/* HEADER */}
                        <TableHead>

                            <TableRow>

                                <TableCell
                                    sx={{
                                        fontWeight: 700,
                                        minWidth: 180,
                                        position: "sticky",
                                        left: 0,
                                        zIndex: 3,
                                        backgroundColor: "#fff",
                                        borderRight:
                                            "1px solid #E2E8F0",
                                    }}
                                >
                                    Product / LOT
                                </TableCell>

                                {formattedMonths.map(
                                    (month, index) => (

                                        <TableCell
                                            key={index}
                                            align="center"
                                            sx={{
                                                fontWeight: 700,
                                                minWidth: 90,
                                                borderRight:
                                                    "1px solid #E2E8F0",
                                                // backgroundColor:
                                                //     index < forecastStartIndex
                                                //         ? "#f1f5f9"
                                                //         : "#fff",
                                            }}
                                        >
                                            {month}
                                        </TableCell>
                                    )
                                )}
                            </TableRow>

                        </TableHead>

                        {/* BODY */}
                        <TableBody>

                            {editableRows.map(
                                (lotGroup, lotIndex) => (

                                    <React.Fragment
                                        key={lotGroup.lot}
                                    >

                                        {/* LOT ROW */}
                                        <TableRow
                                            onClick={() =>
                                                toggleLot(
                                                    lotGroup.lot
                                                )
                                            }
                                            sx={{
                                                cursor: "pointer",
                                                backgroundColor:
                                                    "#f8fafc",
                                            }}
                                        >

                                            <TableCell
                                                sx={{
                                                    fontWeight: 700,
                                                    position: "sticky",
                                                    left: 0,
                                                    zIndex: 2,
                                                    backgroundColor:
                                                        "#f8fafc",
                                                    borderRight:
                                                        "1px solid #E2E8F0",
                                                }}
                                            >
                                                {expandedLots[
                                                    lotGroup.lot
                                                ]
                                                    ? "▼"
                                                    : "▶"}{" "}
                                                {lotGroup.lot}
                                            </TableCell>

                                            {lotGroup.total.map(
                                                (
                                                    value,
                                                    index
                                                ) => (

                                                    <TableCell
                                                        key={index}
                                                        align="center"
                                                        sx={{
                                                            fontWeight: 700,
                                                            borderRight:
                                                                "1px solid #E2E8F0",
                                                            // backgroundColor:
                                                            //     index < forecastStartIndex
                                                            //         ? "#e2e8f0"
                                                            //         : "#fff",

                                                            // backgroundColor:
                                                            //     index < forecastStartIndex
                                                            //         ? "#dbeafe"
                                                            //         : "#bfdbfe",

                                                            backgroundColor: "#f8fafc"
                                                            // color: "#1e3a8a",
                                                        }}
                                                    >
                                                        {formatValue(value)}
                                                    </TableCell>
                                                )
                                            )}
                                        </TableRow>

                                        {/* CHILD ROWS */}
                                        {expandedLots[
                                            lotGroup.lot
                                        ] &&
                                            lotGroup.children.map(
                                                (
                                                    row,
                                                    childIndex
                                                ) => (

                                                    <TableRow
                                                        key={
                                                            childIndex
                                                        }
                                                    >

                                                        <TableCell
                                                            sx={{
                                                                pl: 4,
                                                                position:
                                                                    "sticky",
                                                                left: 0,
                                                                zIndex: 1,
                                                                backgroundColor:
                                                                    "#fff",
                                                                borderRight:
                                                                    "1px solid #E2E8F0",
                                                            }}
                                                        >
                                                            {
                                                                row.label
                                                            }
                                                        </TableCell>

                                                        {row.values.map(
                                                            (
                                                                value,
                                                                valueIndex
                                                            ) => (

                                                                <TableCell
                                                                    key={
                                                                        valueIndex
                                                                    }
                                                                    align="center"
                                                                    sx={{
                                                                        borderRight: "1px solid #E2E8F0",
                                                                        py: "4px",
                                                                        px: 1,
                                                                        backgroundColor:
                                                                            valueIndex < forecastStartIndex
                                                                                ? "#f1f5f9"
                                                                                // : editable
                                                                                //     ? "#f8fbff"
                                                                                : "#fff",
                                                                    }}
                                                                >
                                                                    {renderEditableCell(
                                                                        value,
                                                                        lotIndex,
                                                                        childIndex,
                                                                        valueIndex
                                                                    )}
                                                                </TableCell>
                                                            )
                                                        )}

                                                    </TableRow>
                                                )
                                            )}

                                    </React.Fragment>
                                )
                            )}

                        </TableBody>
                    </Table>
                </TableContainer>
            )}
        </Paper>
    );
}