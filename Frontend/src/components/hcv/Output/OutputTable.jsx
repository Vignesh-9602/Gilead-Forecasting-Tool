import React, { useState, useEffect } from "react";

import {
    Box,
    Table,
    TableHead,
    TableBody,
    TableRow,
    TableCell,
    TableContainer,
    Typography,
} from "@mui/material";

const MONTH_ABBREVIATIONS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

// Turns an ISO date string like "2024-06-01" into "Jun-24" for display.
// Leaves anything that doesn't look like a YYYY-MM date (e.g. "2024 Total"
// yearly headers) untouched.
const formatMonthLabel = (value) => {
    if (typeof value !== "string") return value;

    const match = value.match(/^(\d{4})-(\d{2})/);

    if (!match) return value;

    const [, year, month] = match;
    const monthAbbr = MONTH_ABBREVIATIONS[Number(month) - 1] || month;

    return `${monthAbbr}-${year.slice(-2)}`;
};

const formatCellValue = (value, isShare) => {
    const numeric = Number(value ?? 0);

    if (Number.isNaN(numeric)) return "-";

    return isShare
        ? `${numeric.toFixed(1)}%`
        : Math.round(numeric).toLocaleString();
};

// rows: [{ key, label, metricLabel, values, rowType: 'total'|'group'|'child'|'leaf', children? }]
export default function OutputTable({
    pivotLabel = "Total Volume Base",
    headers = [],
    rows = [],
    metric = "market_volume",
}) {
    const [expandedKeys, setExpandedKeys] = useState({});

    const isShare = metric === "payer_share";

    const formattedHeaders = headers.map(formatMonthLabel);

    useEffect(() => {
        // Default every group row to expanded the first time it appears.
        setExpandedKeys((prev) => {
            const next = { ...prev };
            let changed = false;

            rows.forEach((row) => {
                if (Array.isArray(row.children) && row.children.length > 0 && !(row.key in next)) {
                    next[row.key] = true;
                    changed = true;
                }
            });

            return changed ? next : prev;
        });
    }, [rows]);

    const toggleRow = (key) => {
        setExpandedKeys((prev) => ({
            ...prev,
            [key]: !prev[key],
        }));
    };

    const renderRow = (row) => {
        const hasChildren = Array.isArray(row.children) && row.children.length > 0;
        const isExpanded = expandedKeys[row.key] ?? true;

        const isTotal = row.rowType === "total";
        const isGroup = row.rowType === "group" || hasChildren;
        const isChild = row.rowType === "child";

        const rowBg = isTotal ? "#f1f5f9" : isGroup ? "#f8fafc" : "#fff";

        return (
            <React.Fragment key={row.key}>
                <TableRow sx={{ backgroundColor: rowBg }}>
                    <TableCell
                        onClick={hasChildren ? () => toggleRow(row.key) : undefined}
                        sx={{
                            position: "sticky",
                            left: 0,
                            zIndex: 2,
                            backgroundColor: rowBg,
                            minWidth: 220,
                            maxWidth: 220,
                            fontWeight: isTotal ? 800 : isGroup ? 700 : 500,
                            color: isTotal ? "#1e293b" : isGroup ? "#4F46E5" : "#334155",
                            borderRight: "2px solid #E2E8F0",
                            borderBottom: isTotal ? "2px solid #E2E8F0" : "1px solid #E2E8F0",
                            cursor: hasChildren ? "pointer" : "default",
                            pl: isChild ? 4 : 2,
                        }}
                    >
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                            {hasChildren && (
                                <Box
                                    component="span"
                                    sx={{
                                        width: 14,
                                        fontWeight: 700,
                                        fontSize: "9px",
                                        color: "#4F46E5",
                                        flexShrink: 0,
                                    }}
                                >
                                    {isExpanded ? "▼" : "▶"}
                                </Box>
                            )}
                            <Typography
                                sx={{
                                    fontSize: "12px",
                                    fontWeight: "inherit",
                                    color: "inherit",
                                    whiteSpace: "nowrap",
                                }}
                            >
                                {row.label}
                            </Typography>
                        </Box>
                    </TableCell>

                    {(row.values || []).map((value, index) => (
                        <TableCell
                            key={index}
                            align="right"
                            sx={{
                                minWidth: 90,
                                backgroundColor: rowBg,
                                borderRight: "1px solid #E2E8F0",
                                borderBottom: isTotal ? "2px solid #E2E8F0" : "1px solid #E2E8F0",
                            }}
                        >
                            <Typography
                                sx={{
                                    fontSize: "12px",
                                    fontWeight: isTotal ? 800 : isGroup ? 700 : 500,
                                    color: isGroup && !isTotal ? "#4F46E5" : "#334155",
                                }}
                            >
                                {formatCellValue(value, isShare)}
                            </Typography>
                        </TableCell>
                    ))}
                </TableRow>

                {hasChildren &&
                    isExpanded &&
                    row.children.map((child) => renderRow(child))}
            </React.Fragment>
        );
    };

    return (
        <Box
            sx={{
                backgroundColor: "#fff",
                border: "1px solid #D8DEE8",
                borderRadius: "8px",
                overflowX: "auto",
                position: "relative",
            }}
        >
            {rows.length === 0 ? (
                <Box
                    sx={{
                        height: 120,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "#94a3b8",
                        fontSize: "14px",
                    }}
                >
                    No table data available. Please adjust filters.
                </Box>
            ) : (
                <TableContainer>
                    <Table
                        size="small"
                        sx={{
                            width: "100%",
                            tableLayout: "auto",
                            minWidth: "max-content",
                            borderCollapse: "separate",
                        }}
                    >
                        <TableHead>
                            <TableRow>
                                <TableCell
                                    sx={{
                                        position: "sticky",
                                        left: 0,
                                        top: 0,
                                        zIndex: 5,
                                        backgroundColor: "#f8fafc",
                                        fontWeight: 700,
                                        fontSize: "11px",
                                        color: "#64748b",
                                        minWidth: 220,
                                        maxWidth: 220,
                                        borderRight: "2px solid #E2E8F0",
                                        borderBottom: "2px solid #E2E8F0",
                                    }}
                                >
                                    {pivotLabel}
                                </TableCell>

                                {formattedHeaders.map((header, index) => (
                                    <TableCell
                                        key={index}
                                        align="right"
                                        sx={{
                                            position: "sticky",
                                            top: 0,
                                            zIndex: 4,
                                            backgroundColor: "#f8fafc",
                                            fontWeight: 700,
                                            fontSize: "11px",
                                            color: "#64748b",
                                            minWidth: 90,
                                            borderRight: "1px solid #E2E8F0",
                                            borderBottom: "2px solid #E2E8F0",
                                        }}
                                    >
                                        {header}
                                    </TableCell>
                                ))}
                            </TableRow>
                        </TableHead>

                        <TableBody>{rows.map((row) => renderRow(row))}</TableBody>
                    </Table>
                </TableContainer>
            )}
        </Box>
    );
}