import React, { useState } from "react";
import {
    Box,
    Paper,
    Tabs,
    Tab,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    IconButton,
    Typography,
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import Tooltip from "@mui/material/Tooltip";
import ExcelJS from "exceljs";
import { saveAs } from "file-saver";

import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";

export default function OutputTable({ tableData, activeTab,
    scenario,
    indications,
    lots,
    products,
    startDate,
    endDate, }) {

    // const [activeTab, setActiveTab] = useState(0);

    const [expandedRows, setExpandedRows] =
        useState({});

    if (!tableData) {
        return (
            <Paper
                sx={{
                    mt: 3,
                    p: 4,
                    textAlign: "center",
                    borderRadius: "12px",
                    border: "1px solid #D8DEE8",
                    boxShadow: "none",
                }}
            >
                <Typography>
                    No table data available
                </Typography>
            </Paper>
        );
    }

    const months =
        tableData?.months?.map(
            (month) =>
                new Date(month).toLocaleDateString(
                    "en-US",
                    {
                        month: "short",
                        year: "numeric",
                    }
                )
        ) || [];

    // const indicationData =
    //     outputData?.table?.indication_tab;

    // const lotData =
    //     outputData?.table?.lot_tab;

    // const currentData =
    //     activeTab === 0
    //         ? indicationData
    //         : lotData;
    const currentData = tableData;

    const handleDownloadExcel = async () => {
        if (!tableData) return;

        const workbook = new ExcelJS.Workbook();

        const worksheet =
            workbook.addWorksheet(
                activeTab === "indication"
                    ? "Demand By Indication"
                    : "Demand By LOT"
            );

        // Filters
        worksheet.addRow(["Scenario", scenario]);

        worksheet.addRow([
            "Indications",
            indications?.join(", ")
        ]);

        worksheet.addRow([
            "LOTs",
            lots?.join(", ")
        ]);

        worksheet.addRow([
            "Products",
            products?.join(", ")
        ]);

        worksheet.addRow([
            "Start Date",
            startDate
        ]);

        worksheet.addRow([
            "End Date",
            endDate
        ]);

        worksheet.addRow([]);

        // Header
        worksheet.addRow([
            "Hierarchy Segmentation",
            ...months
        ]);

        // Total row
        const totalRow = worksheet.addRow([
            tableData.hierarchy_label,
            ...(tableData.total_values || [])
        ]);

        totalRow.font = {
            bold: true
        };

        // Main rows
        tableData.rows.forEach((row) => {

            const parentRow =
                worksheet.addRow([
                    row.label,
                    ...(row.values || [])
                ]);

            parentRow.font = {
                bold: true
            };

            row.children?.forEach(
                (child) => {
                    worksheet.addRow([
                        child.label,
                        ...(child.values || [])
                    ]);
                }
            );
        });

        // Styling
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

        worksheet.getRow(8).font = {
            bold: true
        };

        worksheet.getColumn(1).width = 40;

        for (
            let i = 2;
            i <= months.length + 1;
            i++
        ) {
            worksheet.getColumn(i).width = 15;
        }

        const buffer =
            await workbook.xlsx.writeBuffer();

        saveAs(
            new Blob([buffer]),
            activeTab === "indication"
                ? "Demand_By_Indication.xlsx"
                : "Demand_By_LOT.xlsx"
        );
    };

    return (
        <Paper
            sx={{
                mt: 3,
                borderRadius: "8px",
                border: "1px solid #D8DEE8",
                boxShadow: "none",
                overflow: "hidden",
            }}
        >
            {/* <Tabs
                value={activeTab}
                onChange={(e, value) =>
                    setActiveTab(value)
                }
                sx={{
                    px: 2,

                    "& .MuiTab-root": {
                        textTransform: "none",
                        fontWeight: 600,
                        fontSize: "14px",
                    },
                }}
            >
                <Tab label="Demand Summary by Indication" />

                <Tab label="Demand Summary by LOT" />
            </Tabs> */}

            <Box>
                <Box
                    sx={{
                        px: 2,
                        py: 0,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        borderBottom: "1px solid #E2E8F0",
                    }}
                >
                    <Typography
                        sx={{
                            fontWeight: 700,
                            fontSize: "16px",
                        }}
                    >
                        Demand Volume Table
                    </Typography>

                    <Tooltip title="Download Table">
                        <IconButton
                            onClick={handleDownloadExcel}
                        >
                            <DownloadIcon />
                        </IconButton>
                    </Tooltip>
                </Box>
                <TableContainer
                    sx={{
                        overflowX: "auto",
                        maxHeight: 500,
                    }}
                >
                    <Table
                        size="small"
                        sx={{
                            minWidth: 2200,
                        }}
                    >
                        <TableHead>
                            <TableRow>
                                <TableCell
                                    sx={{
                                        minWidth: 340,
                                        fontWeight: 700,
                                        position: "sticky",
                                        left: 0,
                                        zIndex: 2,
                                        backgroundColor: "#f8fafc",
                                        color: "#64748b",
                                        borderRight:
                                            "1px solid #E2E8F0",
                                    }}
                                >
                                    Hierarchy Segmentation
                                    (Demand Volume)
                                </TableCell>

                                {months.map(
                                    (
                                        month,
                                        index
                                    ) => (
                                        <TableCell
                                            key={
                                                month
                                            }
                                            align="center"
                                            sx={{
                                                fontWeight: 700,
                                                minWidth: 110,
                                                whiteSpace:
                                                    "nowrap",
                                                color: "#64748b",
                                                backgroundColor:
                                                    index <
                                                        currentData
                                                            ?.total_values
                                                            ?.length -
                                                        4
                                                        ? "#f8fafc"
                                                        : "#ffffff",
                                                borderRight:
                                                    "1px solid #E2E8F0",
                                            }}
                                        >
                                            {month}
                                        </TableCell>
                                    )
                                )}
                            </TableRow>
                        </TableHead>

                        <TableBody>

                            {/* TOTAL AGGREGATED */}

                            <TableRow>
                                <TableCell
                                    sx={{
                                        position:
                                            "sticky",
                                        left: 0,
                                        zIndex: 1,
                                        backgroundColor:
                                            "#f1f5f9",
                                        fontWeight: 700,
                                        borderRight:
                                            "1px solid #E2E8F0",
                                    }}
                                >
                                    {
                                        currentData?.hierarchy_label
                                    }
                                </TableCell>

                                {currentData?.total_values?.map(
                                    (
                                        value,
                                        index
                                    ) => (
                                        <TableCell
                                            key={
                                                index
                                            }
                                            align="center"
                                            sx={{
                                                fontWeight: 700,
                                                backgroundColor:
                                                    "#f1f5f9",
                                                borderRight:
                                                    "1px solid #E2E8F0",
                                            }}
                                        >
                                            {value.toLocaleString()}
                                        </TableCell>
                                    )
                                )}
                            </TableRow>

                            {/* DEMAND ROWS */}

                            {currentData?.rows?.map(
                                (row) => {

                                    const isExpanded =
                                        expandedRows[
                                        row.label
                                        ] ??
                                        true;

                                    return (
                                        <React.Fragment
                                            key={
                                                row.label
                                            }
                                        >
                                            <TableRow>
                                                <TableCell
                                                    sx={{
                                                        position:
                                                            "sticky",
                                                        left: 0,
                                                        zIndex: 1,
                                                        backgroundColor:
                                                            "#ffffff",
                                                        fontWeight: 700,
                                                        borderRight:
                                                            "1px solid #E2E8F0",
                                                    }}
                                                >
                                                    <Box
                                                        sx={{
                                                            display:
                                                                "flex",
                                                            alignItems:
                                                                "center",
                                                        }}
                                                    >
                                                        <IconButton
                                                            size="small"
                                                            onClick={() =>
                                                                setExpandedRows(
                                                                    (
                                                                        prev
                                                                    ) => ({
                                                                        ...prev,
                                                                        [row.label]:
                                                                            !isExpanded,
                                                                    })
                                                                )
                                                            }
                                                        >
                                                            {isExpanded ? (
                                                                <KeyboardArrowDownIcon />
                                                            ) : (
                                                                <KeyboardArrowRightIcon />
                                                            )}
                                                        </IconButton>

                                                        {
                                                            row.label
                                                        }
                                                    </Box>
                                                </TableCell>

                                                {row.values.map(
                                                    (
                                                        value,
                                                        index
                                                    ) => (
                                                        <TableCell
                                                            key={
                                                                index
                                                            }
                                                            align="center"
                                                            sx={{
                                                                fontWeight: 700,
                                                                borderRight:
                                                                    "1px solid #E2E8F0",
                                                            }}
                                                        >
                                                            {value.toLocaleString()}
                                                        </TableCell>
                                                    )
                                                )}
                                            </TableRow>

                                            {/* PRODUCT ROWS */}

                                            {isExpanded &&
                                                row.children?.map(
                                                    (
                                                        child
                                                    ) => (
                                                        <TableRow
                                                            key={
                                                                child.label
                                                            }
                                                        >
                                                            <TableCell
                                                                sx={{
                                                                    position:
                                                                        "sticky",
                                                                    left: 0,
                                                                    zIndex: 1,
                                                                    pl: 5,
                                                                    backgroundColor:
                                                                        "#ffffff",
                                                                    borderRight:
                                                                        "1px solid #E2E8F0",
                                                                }}
                                                            >
                                                                {
                                                                    child.label
                                                                }
                                                            </TableCell>

                                                            {child.values.map(
                                                                (
                                                                    value,
                                                                    index
                                                                ) => (
                                                                    <TableCell
                                                                        key={
                                                                            index
                                                                        }
                                                                        align="center"
                                                                        sx={{
                                                                            borderRight:
                                                                                "1px solid #E2E8F0",
                                                                        }}
                                                                    >
                                                                        {value.toLocaleString()}
                                                                    </TableCell>
                                                                )
                                                            )}
                                                        </TableRow>
                                                    )
                                                )}
                                        </React.Fragment>
                                    );
                                }
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Box>
        </Paper>
    );
}