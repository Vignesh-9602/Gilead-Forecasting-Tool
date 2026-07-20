import React, { useState } from "react";

import {
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    Box,
    Typography,
    ToggleButton,
    ToggleButtonGroup,
    FormControl,
    Select,
    MenuItem,
} from "@mui/material";

import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

import IconButton from "@mui/material/IconButton";

import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import dayjs from "dayjs";

export default function HIVOutputTable({
    tableData,
    viewMode,
    setViewMode,
    selectedMetric,
    setSelectedMetric,
    metricOptions = [],
}) {

    const [expandedRows, setExpandedRows] = useState({});

    if (!tableData) {
        return null;
    }

    const headers = tableData.headers || [];
    const rows = tableData.rows || [];

    // const [expandedRows, setExpandedRows] = useState({});
    const handleToggle = (key) => {
        setExpandedRows((prev) => ({
            ...prev,
            [key]: !prev[key],
        }));
    };

    const renderHierarchyRows = (
        row,
        level = 0,
        rowKey = ""
    ) => {

        const hasChildren =
            row.children &&
            row.children.length > 0;

        const expanded =
            expandedRows[rowKey] ?? true;

        const isTotalRow =
            row.label?.toLowerCase().includes("grand total") ||
            (hasChildren && level === 0);

        return (
            <React.Fragment key={rowKey}>

                <TableRow hover>

                    <TableCell
                        sx={{
                            position: "sticky",
                            left: 0,
                            background: "#fff",
                            zIndex: 1,
                            minWidth: 280,
                        }}
                    >
                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                pl: level * 3,
                            }}
                        >

                            {hasChildren ? (

                                <IconButton
                                    size="small"
                                    onClick={() =>
                                        handleToggle(rowKey)
                                    }
                                >
                                    {expanded ? (
                                        <KeyboardArrowDownIcon fontSize="small" />
                                    ) : (
                                        <KeyboardArrowRightIcon fontSize="small" />
                                    )}
                                </IconButton>

                            ) : (

                                <Box sx={{ width: 40 }} />

                            )}

                            <Typography
                                sx={{
                                    fontWeight: isTotalRow ? 700 : 500,
                                }}
                            >
                                {row.label}
                            </Typography>

                        </Box>
                    </TableCell>

                    {row.values.map((value, index) => (

                        <TableCell
                            key={index}
                            align="center"
                            sx={{
                                fontWeight: isTotalRow ? 700 : 500,
                            }}
                        >
                            {typeof value === "number"
                                ? value.toLocaleString()
                                : value}
                        </TableCell>

                    ))}

                </TableRow>

                {hasChildren &&
                    expanded &&
                    row.children.map((child, index) =>
                        renderHierarchyRows(
                            child,
                            level + 1,
                            `${rowKey}-${index}`
                        )
                    )}

            </React.Fragment>
        );
    };

    return (
        <Box
            sx={{
                mt: 3,
                border: "1px solid #D8DEE8",
                borderRadius: "12px",
                overflow: "hidden",
                background: "#fff",
            }}
        >
            <Box
                sx={{
                    px: 2,
                    py: 2,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    borderBottom: "1px solid #E2E8F0",
                }}
            >
                <Typography
                    sx={{
                        fontWeight: 700,
                        fontSize: 16,
                    }}
                >
                    Output Table
                </Typography>

                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 2,
                    }}
                >
                    <Box
                        sx={{
                            display: "flex",
                            backgroundColor: "#E2E8F0",
                            borderRadius: "8px",
                            p: "2px",
                        }}
                    >
                        {[
                            {
                                label: "Monthly",
                                value: "monthly",
                            },
                            {
                                label: "Yearly",
                                value: "yearly",
                            },
                        ].map((tab) => (
                            <Box
                                key={tab.value}
                                onClick={() => setViewMode(tab.value)}
                                sx={{
                                    px: 2,
                                    py: 0.8,
                                    cursor: "pointer",
                                    fontSize: "13px",
                                    fontWeight: 600,
                                    borderRadius: "6px",

                                    backgroundColor:
                                        viewMode === tab.value
                                            ? "#fff"
                                            : "transparent",

                                    color:
                                        viewMode === tab.value
                                            ? "#4F46E5"
                                            : "#64748B",

                                    transition: ".2s",

                                    "&:hover": {
                                        backgroundColor:
                                            viewMode === tab.value
                                                ? "#fff"
                                                : "#F1F5F9",
                                    },
                                }}
                            >
                                {tab.label}
                            </Box>
                        ))}
                    </Box>

                    <FormControl
                        size="small"
                        sx={{
                            minWidth: 220,

                            "& .MuiOutlinedInput-root": {
                                height: "35px",
                                borderRadius: "8px",
                                background: "#fff",
                            },
                        }}
                    >
                        <Select
                            value={selectedMetric}
                            onChange={(e) =>
                                setSelectedMetric(e.target.value)
                            }
                        >
                            {metricOptions.map((option) => (
                                <MenuItem
                                    key={option.value}
                                    value={option.value}
                                >
                                    {option.label}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                </Box>
            </Box>

            <Box sx={{ p: 2 }}>

                <TableContainer
                    sx={{
                        overflowX: "auto",
                        maxHeight: 520,
                        border: "1px solid #E2E8F0",
                        borderRadius: "12px",
                    }}
                >
                    <Table
                        stickyHeader
                        size="small"
                        sx={{
                            width: "100%",
                            tableLayout: "fixed",
                            minWidth: "max-content",
                            borderCollapse: "collapse",

                            "& .MuiTableCell-root": {
                                borderRight: "1px solid #E2E8F0",
                                borderBottom: "1px solid #E2E8F0",
                                padding: "10px 8px",
                            },

                            "& .MuiTableRow-root:hover": {
                                backgroundColor: "#F8FAFC",
                            },
                        }}
                    >

                        <TableHead>
                            <TableRow>

                                {headers.map((header, index) => {

                                    const displayHeader =
                                        /^\d{4}-\d{2}(-\d{2})?$/.test(header)
                                            ? dayjs(header).format("MMM-YY")
                                            : header;

                                    return (
                                        <TableCell
                                            key={header}
                                            align={index === 0 ? "left" : "center"}
                                            sx={{
                                                position: "sticky",
                                                left: index === 0 ? 0 : undefined,
                                                zIndex: index === 0 ? 5 : 2,

                                                backgroundColor:
                                                    index === 0
                                                        ? "#F8FAFC"
                                                        : index < tableData.forecast_start_index
                                                            ? "#F8FAFC"
                                                            : "#FFFFFF",

                                                minWidth: index === 0 ? 200 : 95,
                                                width: index === 0 ? 200 : 95,

                                                fontWeight: 700,
                                                color: "#64748B",
                                            }}
                                        >
                                            {displayHeader}
                                        </TableCell>
                                    );

                                })}
                            </TableRow>
                        </TableHead>

                        <TableBody>

                            {tableData.type === "hierarchy"

                                ? rows.map((row, index) =>
                                    renderHierarchyRows(
                                        row,
                                        0,
                                        String(index)
                                    )
                                )

                                : rows.map((row) => (

                                    <TableRow
                                        key={row.label}
                                    >

                                        <TableCell
                                            sx={{
                                                position: "sticky",
                                                left: 0,
                                                backgroundColor: "#FFFFFF",
                                                zIndex: 1,
                                                minWidth: 280,
                                                fontWeight: 600,
                                                borderRight: "1px solid #E2E8F0",
                                            }}
                                        >
                                            {row.label}
                                        </TableCell>

                                        {row.values.map((value, index) => (

                                            <TableCell
                                                key={index}
                                                align="center"
                                                sx={{
                                                    backgroundColor:
                                                        index < tableData.forecast_start_index
                                                            ? "#F8FAFC"
                                                            : "#FFFFFF",
                                                    fontWeight: 500,
                                                }}
                                            >
                                                {typeof value === "number"
                                                    ? value.toLocaleString()
                                                    : value}
                                            </TableCell>

                                        ))}

                                    </TableRow>

                                ))}

                        </TableBody>

                    </Table>
                </TableContainer>

            </Box>
        </Box>
    );
}