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

const SELECTED_COLOR = "#F59E0B"; // Amber — matches the chart's highlight color
const SELECTED_BG = "#FFF7ED";

// rows: [{ key, label, metricLabel, values, rowType: 'total'|'group'|'child'|'leaf', children? }]
export default function OutputTable({
    pivotLabel = "Total Volume Base",
    headers = [],
    rows = [],
    metric = "market_volume",
    selectedPayer,
    selectedProduct,
    forecastStartIndex,
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

    // Does this row's own label match the currently selected payer or product?
    // Flat-table rows carry a trailing "(BASE Scenario)" suffix (e.g.
    // "Cash (BASE Scenario)"), so compare against the base name only —
    // hierarchy rows are already bare names ("Cash", "ASGA") and pass
    // through this split unchanged.
    const selfMatches = (row) => {
        if (!row.label) return false;
        const baseLabel = row.label.split(" (")[0].trim().toLowerCase();
        return (
            baseLabel === selectedPayer?.toLowerCase() ||
            baseLabel === selectedProduct?.toLowerCase()
        );
    };

    // ancestorMatched: whether this row's parent group was itself highlighted.
    // Called with `true` for every top-level row (rows.map below) — flat
    // tables (Payer/Product Distribution) have no real parent to check, and
    // hierarchy roots' own group-level self-match is what actually gates
    // them. Only recursive calls into row.children pass the parent's real
    // isSelected, so a leaf like "ASGA" only lights up inside the specific
    // selected payer's group, not under every payer's ASGA row — mirrors
    // ModelInput.jsx's isAppliedParent / isAppliedChild cross-check.
    const renderRow = (row, ancestorMatched = false) => {
        const hasChildren = Array.isArray(row.children) && row.children.length > 0;
        const isExpanded = expandedKeys[row.key] ?? true;

        const isTotal = row.rowType === "total";
        const isGroup = row.rowType === "group" || hasChildren;
        const isChild = row.rowType === "child";

        const matchesHere = selfMatches(row);
        const isSelected = isGroup ? matchesHere : ancestorMatched && matchesHere;

        const rowBg = isSelected
            ? SELECTED_BG
            : isTotal
                ? "#f1f5f9"
                : isGroup
                    ? "#f8fafc"
                    : "#fff";

        const labelColor = isSelected
            ? SELECTED_COLOR
            : isTotal
                ? "#1e293b"
                : "#334155";

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
                            fontWeight: isTotal || isSelected ? 700 : 400,
                            color: labelColor,
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
                                        color: isSelected ? SELECTED_COLOR : "#64748B",
                                        flexShrink: 0,
                                    }}
                                >
                                    {isExpanded ? "▼" : "▶"}
                                </Box>
                            )}
                            <Typography
                                sx={{
                                    fontSize: 14,
                                    fontWeight: "inherit",
                                    color: "inherit",
                                    whiteSpace: "nowrap",
                                }}
                            >
                                {row.label}
                            </Typography>
                        </Box>
                    </TableCell>

                    {(row.values || []).map((value, index) => {
                        const isForecastColumn =
                            typeof forecastStartIndex === "number" && index >= forecastStartIndex;

                        // The highlight only applies to forecast columns —
                        // history columns keep their normal shading even on
                        // a selected row, same as ModelInput.jsx.
                        const highlightThisCell = isSelected && isForecastColumn;

                        const cellBg = highlightThisCell
                            ? SELECTED_BG
                            : isForecastColumn
                                ? "#FFFFFF"
                                : "#F1F5F9";

                        const cellColor = highlightThisCell
                            ? SELECTED_COLOR
                            : "#334155";

                        return (
                            <TableCell
                                key={index}
                                align="right"
                                sx={{
                                    minWidth: 90,
                                    backgroundColor: cellBg,
                                    borderRight: "1px solid #E2E8F0",
                                    borderBottom: isTotal ? "2px solid #E2E8F0" : "1px solid #E2E8F0",
                                }}
                            >
                                <Typography
                                    sx={{
                                        fontSize: 14,
                                        fontWeight: isTotal || highlightThisCell ? 700 : 400,
                                        color: cellColor,
                                    }}
                                >
                                    {formatCellValue(value, isShare)}
                                </Typography>
                            </TableCell>
                        );
                    })}
                </TableRow>

                {hasChildren &&
                    isExpanded &&
                    row.children.map((child) => renderRow(child, isSelected))}
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
                                        fontSize: 14,
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
                                            fontSize: 14,
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

                        <TableBody>{rows.map((row) => renderRow(row, true))}</TableBody>
                    </Table>
                </TableContainer>
            )}
        </Box>
    );
}