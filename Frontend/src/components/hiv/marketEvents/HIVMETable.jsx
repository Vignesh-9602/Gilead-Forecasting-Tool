import React, { useState, useEffect } from "react";

import {
    Box,
    Paper,
    Typography,
    Button,
    FormControl,
    Select,
    MenuItem,
    Table,
    TableHead,
    TableBody,
    TableRow,
    TableCell,
    TableContainer,
} from "@mui/material";

import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";

import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import dayjs from "dayjs";

export default function HIVImpactCurveTable({
    tableData,
    metricFilters,
    currentMetricData,
    selectedTableView,
    setSelectedTableView,
    selectedMetric,
    setSelectedMetric,
    selectedView,
    setSelectedView,
    activeTab,
    editedTableRows,
    setEditedTableRows,
    onEditRefresh,
    setEditedFields,
    selectedMarket,
    selectedProduct,
}) {

    const [editable, setEditable] = useState(false);

    const [editableRows, setEditableRows] = useState([]);

    const [originalRows, setOriginalRows] = useState([]);

    const isHierarchy = tableData?.type === "hierarchy";

    const [expandedRows, setExpandedRows] = useState({});

    const viewOptions = [
        {
            label: "Monthly",
            value: "monthly",
        },
        {
            label: "Yearly",
            value: "yearly",
        },
    ];

    useEffect(() => {

        if (!tableData) return;

        const cloned = JSON.parse(
            JSON.stringify(tableData.rows)
        );

        setEditableRows(cloned);
        setEditedTableRows(cloned);
        setOriginalRows(cloned);

    }, [tableData]);

    useEffect(() => {

        setEditable(false);

    }, [selectedView]);

    useEffect(() => {

        if (!isHierarchy)
            return;

        const expanded = {};

        editableRows.forEach((row) => {

            if (row.children?.length) {

                expanded[row.label] = true;

            }

        });

        setExpandedRows(expanded);

    }, [editableRows, isHierarchy]);

    const toggleRow = (label) => {

        setExpandedRows((prev) => ({

            ...prev,

            [label]: !prev[label],

        }));

    };

    const handleExpandAll = () => {

        const expanded = {};

        editableRows.forEach((row) => {

            expanded[row.label] = true;

        });

        setExpandedRows(expanded);

    };

    const handleCollapseAll = () => {

        const collapsed = {};

        editableRows.forEach((row) => {

            collapsed[row.label] = false;

        });

        setExpandedRows(collapsed);

    };

    if (
        !tableData ||
        !editableRows?.length
    ) {
        return (
            <Paper
                sx={{
                    mt: 3,
                    p: 4,
                    borderRadius: "16px",
                    border: "1px solid #D8DEE8",
                    textAlign: "center",
                }}
            >
                No table data available.
            </Paper>
        );
    }

    const handleCancel = () => {

        setEditableRows(
            JSON.parse(
                JSON.stringify(originalRows)
            )
        );

        setEditable(false);

    };

    const handleCellChange = (
        rowIndex,
        valueIndex,
        value,
        childIndex = null
    ) => {

        if (!/^\d*\.?\d*$/.test(value)) {
            return;
        }

        const updated = JSON.parse(
            JSON.stringify(editableRows)
        );

        if (childIndex !== null) {

            updated[rowIndex]
                .children[childIndex]
                .values[valueIndex] = value;

        } else {

            updated[rowIndex]
                .values[valueIndex] = value;

        }

        setEditableRows(updated);
        setEditedTableRows(updated);

    };

    const isHighlightedRow = (
        row,
        parentRow = null
    ) => {

        const rowLabel =
            row.label?.toLowerCase();

        const parentLabel =
            parentRow?.label?.toLowerCase();

        const market =
            selectedMarket?.toLowerCase();

        const product =
            selectedProduct?.toLowerCase();

        switch (activeTab) {

            case "overall_event":

                return false;

            // ---------------- CHANNEL EVENT ----------------

            case "market_event":

                switch (selectedTableView) {

                    // Market Level
                    case "market_level":

                        return rowLabel === market;

                    // Product -> Market
                    case "product_market_level":

                        return (
                            parentLabel === product &&
                            rowLabel === market
                        );

                    default:

                        return false;
                }

            // ---------------- PRODUCT EVENT ----------------

            case "product_event":

                switch (selectedTableView) {

                    // Product Level
                    case "product_level":

                        return rowLabel === product;

                    // Market -> Product
                    case "market_product_level":

                        return (
                            parentLabel === market &&
                            rowLabel === product
                        );

                    default:

                        return false;
                }

            default:

                return false;
        }

    };

    const renderEditableCell = (
        value,
        row,
        rowIndex,
        valueIndex,
        childIndex = null,
        level = 0
    ) => {

        const isMarketShare = selectedMetric === "market_share";

        const isOverallEvent = activeTab === "overall_event";

        const isOverallRow = row.label === "Overall";

        const canEdit =
            editable &&
            selectedView === "monthly" &&
            isMarketShare &&
            !(
                !isHierarchy &&
                isOverallRow
            ) &&
            (
                !isHierarchy
                    ? true
                    : childIndex !== null
            );

        if (!canEdit) {
            return (
                <Typography
                    sx={{
                        fontSize: "13px",

                        fontWeight:
                            level === 0
                                ? 700
                                : 500,

                        color:
                            level === 0
                                ? "#1E293B"
                                : "#475569",

                        lineHeight: "28px",
                    }}
                >
                    {formatCellValue(value)}
                </Typography>
            );
        }

        return (

            <input

                value={value}

                onChange={(e) =>
                    handleCellChange(
                        rowIndex,
                        valueIndex,
                        e.target.value,
                        childIndex
                    )
                }

                style={{

                    width: "100%",

                    maxWidth: "72px",

                    minWidth: "56px",

                    height: "28px",

                    padding: "2px 6px",

                    boxSizing: "border-box",

                    display: "block",

                    margin: "0 auto",

                    border: "1px solid #93C5FD",

                    borderRadius: "4px",

                    background: "#EFF6FF",

                    textAlign: "center",

                    fontSize: "13px",

                    fontFamily: "inherit",

                    lineHeight: "20px",

                    outline: "none",

                }}

            />

        );

    };

    const renderRow = (
        row,
        rowIndex,
        level = 0,
        childIndex = null,
        parentRow = null
    ) => {

        const highlighted =
            isHighlightedRow(
                row,
                parentRow
            );

        return (
            <>
                <React.Fragment
                    key={`${rowIndex}-${childIndex}-${row.label}`}
                >

                    <TableRow>

                        <TableCell
                            sx={{
                                position: "sticky",
                                left: 0,
                                zIndex: 2,
                                minWidth: 180,
                                width: 180,
                                backgroundColor:
                                    highlighted
                                        ? "#FFFBEB"
                                        : "#F8FAFC",

                                color:
                                    highlighted
                                        ? "#F59E0B"
                                        : "#334155",

                                fontWeight: 700,
                            }}
                        >

                            <Box
                                sx={{
                                    display: "flex",
                                    alignItems: "center",
                                    pl: level === 0 ? 0 : 1.5,
                                }}
                            >

                                {isHierarchy &&
                                    row.children?.length > 0 && (

                                        <IconButton
                                            size="small"
                                            onClick={() =>
                                                toggleRow(row.label)
                                            }
                                            sx={{
                                                p: 0.25,
                                                mr: 0.5,
                                                ml: -0.5,
                                            }}
                                        >

                                            {expandedRows[row.label]
                                                ? (
                                                    <KeyboardArrowDownIcon
                                                        sx={{
                                                            fontSize: 18,
                                                        }}
                                                    />
                                                )
                                                : (
                                                    <KeyboardArrowDownIcon
                                                        sx={{
                                                            fontSize: 18,
                                                        }}
                                                    />
                                                )}

                                        </IconButton>

                                    )}

                                {row.label}

                            </Box>

                        </TableCell>

                        {row.values.map((value, index) => (

                            <TableCell
                                key={index}
                                align="center"
                                sx={{

                                    backgroundColor:

                                        highlighted

                                            ? "#FFFBEB"

                                            : index <
                                                tableData.forecast_start_index

                                                ? "#F8FAFC"

                                                : "#FFFFFF",
                                }}
                            >

                                {renderEditableCell(
                                    value,
                                    row,
                                    rowIndex,
                                    index,
                                    childIndex,
                                    level
                                )}

                            </TableCell>

                        ))}

                    </TableRow>

                    {isHierarchy &&
                        expandedRows[row.label] &&
                        row.children?.map(
                            (child, idx) =>
                                renderRow(
                                    child,
                                    rowIndex,
                                    level + 1,
                                    idx,
                                    row
                                )
                        )}

                </React.Fragment>
            </>
        )
    };

    const viewOptionsLevel = currentMetricData?.view_options || [];

    const getEditedFields = () => {

        const editedFields = [];

        editableRows.forEach((row, rowIndex) => {

            if (row.children?.length) {

                row.children.forEach((child, childIndex) => {

                    const originalChild =
                        originalRows[rowIndex]?.children?.[childIndex];

                    const isEdited =
                        JSON.stringify(child.values) !==
                        JSON.stringify(originalChild?.values);

                    if (isEdited) {
                        editedFields.push(child.label);
                    }

                });

            } else {

                const originalRow = originalRows[rowIndex];

                const isEdited =
                    JSON.stringify(row.values) !==
                    JSON.stringify(originalRow?.values);

                if (isEdited) {
                    editedFields.push(row.label);
                }

            }

        });

        return editedFields;

    };

    const handleSave = async () => {

        const editedFields = getEditedFields();

        const success = await onEditRefresh(editedFields);

        if (success) {

            setOriginalRows(
                JSON.parse(JSON.stringify(editedTableRows))
            );

            setEditable(false);

        }

    };

    const formatCellValue = (value) => {
        if (
            value === null ||
            value === undefined ||
            value === ""
        ) {
            return "";
        }

        // While editing, don't append %
        if (editable) {
            return value;
        }

        if (selectedMetric === "market_share") {
            return `${value}%`;
        }

        return Number(value).toLocaleString();
    };

    return (

        <Paper
            sx={{
                mt: 3,
                border: "1px solid #D8DEE8",
                borderRadius: "16px",
                boxShadow: "none",
                overflow: "hidden",
            }}
        >

            {/* Header */}

            <Box
                sx={{
                    px: 2.5,
                    py: 2,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 2,
                    borderBottom: "1px solid #E5E7EB",
                }}
            >

                {/* Left */}

                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 2,
                    }}
                >

                    <Typography
                        sx={{
                            fontSize: 16,
                            fontWeight: 700,
                        }}
                    >
                        Impact Curve Metrics Table
                    </Typography>

                    {isHierarchy && (

                        <>

                            <Tooltip title="Expand All">

                                <IconButton
                                    size="small"
                                    onClick={handleExpandAll}
                                >

                                    <UnfoldMoreIcon />

                                </IconButton>

                            </Tooltip>

                            <Tooltip title="Collapse All">

                                <IconButton
                                    size="small"
                                    onClick={handleCollapseAll}
                                >

                                    <UnfoldLessIcon />

                                </IconButton>

                            </Tooltip>

                        </>

                    )}

                </Box>

                {/* Right */}

                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1.5,
                        flexWrap: "wrap",
                    }}
                >
                    {viewOptionsLevel.length > 1 && (

                        <FormControl
                            size="small"
                            sx={{
                                minWidth: 220,

                                "& .MuiOutlinedInput-root": {
                                    height: "35px",
                                    borderRadius: "8px",
                                    backgroundColor: "#fff",
                                },
                            }}
                        >
                            <Select
                                value={selectedTableView}
                                onChange={(e) =>
                                    setSelectedTableView(e.target.value)
                                }
                            >
                                {(currentMetricData?.view_options || []).map((item) => (
                                    <MenuItem
                                        key={item.value}
                                        value={item.value}
                                    >
                                        {item.label}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    )}

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
                                onClick={() =>
                                    setSelectedView(tab.value)
                                }
                                sx={{
                                    px: 2,
                                    py: 0.8,
                                    cursor: "pointer",
                                    fontSize: "13px",
                                    fontWeight: 600,
                                    borderRadius: "6px",
                                    backgroundColor:
                                        selectedView === tab.value
                                            ? "#fff"
                                            : "transparent",
                                    color:
                                        selectedView === tab.value
                                            ? "#4F46E5"
                                            : "#64748B",
                                    transition: ".2s",

                                    "&:hover": {
                                        backgroundColor:
                                            selectedView === tab.value
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
                                backgroundColor: "#fff",
                            },
                        }}
                    >

                        <Select
                            value={selectedMetric}
                            onChange={(e) =>
                                setSelectedMetric(
                                    e.target.value
                                )
                            }
                        >

                            {metricFilters.map((item) => (

                                <MenuItem
                                    key={item.value}
                                    value={item.value}
                                >
                                    {item.label}
                                </MenuItem>

                            ))}

                        </Select>

                    </FormControl>

                    <Button
                        variant="contained"
                        disabled={
                            !editable ||
                            selectedMetric === "market_volume"
                        }
                        onClick={handleSave}
                        sx={{
                            height: "35px",
                            borderRadius: "8px",
                            textTransform: "none",
                        }}
                    >
                        Save
                    </Button>

                    <Button
                        variant="outlined"
                        onClick={() => setEditable(true)}
                        sx={{
                            height: "35px",
                            borderRadius: "8px",
                            textTransform: "none",
                        }}
                        disabled={
                            editable ||
                            selectedMetric === "market_volume" ||
                            selectedView === "yearly" ||
                            activeTab === "overall_event"
                        }
                    >
                        {editable ? "Editing..." : "Edit Changes"}
                    </Button>

                    <Button
                        variant="outlined"
                        disabled={
                            !editable ||
                            selectedMetric === "market_volume"
                        }
                        onClick={handleCancel}
                        sx={{
                            height: "35px",
                            borderRadius: "8px",
                            textTransform: "none",
                        }}
                    >
                        Cancel
                    </Button>

                </Box>

            </Box>

            {/* Table Placeholder */}
            <TableContainer
                sx={{
                    overflowX: "auto",
                    // borderTop: "1px solid #E2E8F0",
                    // maxHeight: 420,

                    // "&::-webkit-scrollbar": {
                    //     height: 8,
                    //     width: 8,
                    // },

                    // "&::-webkit-scrollbar-thumb": {
                    //     background: "#CBD5E1",
                    //     borderRadius: "8px",
                    // },
                }}
            >

                <Table
                    stickyHeader
                    size="small"
                    sx={{
                        width: "100%",
                        tableLayout: "fixed",
                        minWidth: "max-content",

                        "& .MuiTableCell-root": {
                            borderRight: "1px solid #D6DEE8",
                            borderBottom: "1px solid #D6DEE8",
                        },
                    }}
                >
                    <TableHead>

                        <TableRow>

                            <TableCell
                                sx={{
                                    position: "sticky",
                                    left: 0,
                                    zIndex: 5,

                                    backgroundColor: "#ffffff",

                                    fontWeight: 700,

                                    minWidth: 180,
                                    width: 180,

                                    color: "#334155",
                                }}
                            >
                                Market
                            </TableCell>

                            {tableData.headers.map((header, index) => {

                                const displayHeader =
                                    /^\d{4}-\d{2}-\d{2}$/.test(header)
                                        ? dayjs(header).format("MMM-YY")
                                        : header;

                                return (
                                    <TableCell
                                        key={index}
                                        align="center"
                                        sx={{
                                            minWidth: 95,
                                            width: 95,
                                            padding: "10px 8px",

                                            fontWeight: 700,
                                            color: "#334155",

                                            backgroundColor:
                                                index < tableData.forecast_start_index
                                                    ? "#F8FAFC"
                                                    : "#FFFFFF",

                                            whiteSpace: "nowrap",
                                            wordBreak: "keep-all",
                                            overflow: "hidden",
                                            textOverflow: "ellipsis",
                                        }}
                                    >
                                        {displayHeader}
                                    </TableCell>
                                );

                            })}

                        </TableRow>

                    </TableHead>

                    <TableBody>

                        {editableRows.map((row, index) =>
                            renderRow(row, index)
                        )}

                    </TableBody>

                </Table>

            </TableContainer>
        </Paper>

    );

}