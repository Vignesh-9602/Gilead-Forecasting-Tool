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
} from "@mui/material";

import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";

export default function OutputTable() {

    const [activeTab, setActiveTab] = useState(0);

    const [expandedRows, setExpandedRows] = useState({
        "TNBC Total Demand": true,
        "1L Total Demand": true,
    });

    const months = [
        "Jan 2025 ",
        "Feb 2025 ",
        "Mar 2025 ",
        "Apr 2025 ",
        "May 2025 ",
        "Jun 2025 ",
        "Jul 2025 ",
        "Aug 2025 ",
        "Sep 2025 ",
        "Oct 2025 ",
        "Nov 2025 ",
    ];

    const MOCK_TABLE_RESPONSE = {
        indication_tab: {
            hierarchy_label:
                "Total Aggregated Demand (By Indication)",

            rows: [
                {
                    label: "TNBC Total Demand",

                    values: [
                        15000,
                        15500,
                        15800,
                        16200,
                        16600,
                        17100,
                        17500,
                        18000,
                        18400,
                        18900,
                        19300,
                    ],

                    children: [
                        {
                            label: "Trodelvy",

                            values: [
                                15000,
                                15500,
                                15800,
                                16200,
                                16600,
                                17100,
                                17500,
                                18000,
                                18400,
                                18900,
                                19300,
                            ],
                        },
                    ],
                },
            ],
        },

        lot_tab: {
            hierarchy_label:
                "Total Aggregated Demand (By LOT)",

            rows: [
                {
                    label: "1L Total Demand",

                    values: [
                        14000,
                        14300,
                        14600,
                        14900,
                        15200,
                        15500,
                        15800,
                        16100,
                        16400,
                        16800,
                        17100,
                    ],

                    children: [
                        {
                            label: "Trodelvy",

                            values: [
                                14000,
                                14300,
                                14600,
                                14900,
                                15200,
                                15500,
                                15800,
                                16100,
                                16400,
                                16800,
                                17100,
                            ],
                        },
                    ],
                },
            ],
        },
    };

    const currentData =
        activeTab === 0
            ? MOCK_TABLE_RESPONSE.indication_tab
            : MOCK_TABLE_RESPONSE.lot_tab;

    return (
        <Paper
            sx={{
                mt: 3,
                borderRadius: "16px",
                border: "1px solid #D8DEE8",
                boxShadow: "none",
                overflow: "hidden",
            }}
        >
            <Tabs
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
            </Tabs>

            <Box sx={{ p: 2 }}>
                <TableContainer
                    sx={{
                        overflowX: "auto",
                        maxHeight: 500,
                    }}
                >
                    <Table
                        size="small"
                        sx={{
                            minWidth: 1800,
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
                                        backgroundColor: "#f1f5f9",
                                        color: "#64748b",
                                        borderRight: "1px solid #E2E8F0",
                                        py: "2px",
                                        height: "28px",
                                    }}
                                >
                                    Hierarchy Segmentation (Demand Volume)
                                </TableCell>

                                {months.map((month, index) => (
                                    <TableCell
                                        key={month}
                                        align="center"
                                        sx={{
                                            fontWeight: 700,
                                            minWidth: 110,
                                            whiteSpace: "nowrap",
                                            color: "#64748b",
                                            backgroundColor:
                                                index < 6
                                                    ? "#f1f5f9"
                                                    : "#ffffff",
                                            borderRight: "1px solid #E2E8F0",
                                            py: "2px",
                                            height: "28px",
                                        }}
                                    >
                                        {month}
                                    </TableCell>
                                ))}
                            </TableRow>
                        </TableHead>

                        <TableBody>

                            {/* PARENT */}

                            <TableRow>
                                <TableCell
                                    sx={{
                                        position: "sticky",
                                        left: 0,
                                        zIndex: 1,
                                        backgroundColor: "#f1f5f9",
                                        color: "#000",
                                        fontWeight: 700,
                                        borderRight: "1px solid #E2E8F0",
                                    }}
                                >
                                    {currentData.hierarchy_label}
                                </TableCell>

                                {currentData.rows[0].values.map(
                                    (value, index) => (
                                        <TableCell
                                            key={index}
                                            align="center"
                                            sx={{
                                                color: "#000",
                                                fontWeight: 700,
                                                backgroundColor:
                                                    index < 6
                                                        ? "#f1f5f9"
                                                        : "#ffffff",
                                                borderRight: "1px solid #E2E8F0",
                                                py: "2px",
                                                height: "28px",
                                            }}
                                        >
                                            {value.toLocaleString()}
                                        </TableCell>
                                    )
                                )}
                            </TableRow>

                            {/* CHILD */}

                            {currentData.rows.map((row) => {

                                const isExpanded =
                                    expandedRows[row.label];

                                return (
                                    <React.Fragment
                                        key={row.label}
                                    >
                                        <TableRow>
                                            <TableCell
                                                sx={{
                                                    position: "sticky",
                                                    left: 0,
                                                    zIndex: 1,
                                                    backgroundColor: "#f1f5f9",
                                                    color: "#000",
                                                    fontWeight: 700,
                                                    borderRight: "1px solid #E2E8F0",
                                                }}
                                            >
                                                <Box
                                                    sx={{
                                                        display: "flex",
                                                        alignItems: "center",
                                                    }}
                                                >
                                                    <IconButton
                                                        size="small"
                                                        onClick={() =>
                                                            setExpandedRows(
                                                                (prev) => ({
                                                                    ...prev,
                                                                    [row.label]:
                                                                        !prev[
                                                                        row.label
                                                                        ],
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

                                                    {row.label}
                                                </Box>
                                            </TableCell>

                                            {row.values.map(
                                                (
                                                    value,
                                                    index
                                                ) => (
                                                    <TableCell
                                                        key={index}
                                                        align="center"
                                                        sx={{
                                                            color: "#000",
                                                            fontWeight: 700,
                                                            backgroundColor:
                                                                index < 6
                                                                    ? "#f1f5f9"
                                                                    : "#ffffff",
                                                            borderRight: "1px solid #E2E8F0",
                                                            py: "2px",
                                                            height: "28px",
                                                        }}
                                                    >
                                                        {value.toLocaleString()}
                                                    </TableCell>
                                                )
                                            )}
                                        </TableRow>

                                        {/* GRAND CHILD */}

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
                                                                position: "sticky",
                                                                left: 0,
                                                                zIndex: 1,
                                                                pl: 5,
                                                                backgroundColor: "#ffffff",
                                                                borderRight: "1px solid #E2E8F0",
                                                            }}
                                                        >
                                                            {child.label}
                                                        </TableCell>

                                                        {child.values.map(
                                                            (
                                                                value,
                                                                index
                                                            ) => (
                                                                <TableCell
                                                                    key={index}
                                                                    align="center"
                                                                    sx={{
                                                                        backgroundColor:
                                                                            index < 6
                                                                                ? "#f8fafc"
                                                                                : "#ffffff",
                                                                        borderRight: "1px solid #E2E8F0",
                                                                        py: "2px",
                                                                        height: "28px",
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
                            })}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Box>
        </Paper>
    );
}