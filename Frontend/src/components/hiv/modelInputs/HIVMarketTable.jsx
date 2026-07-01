import React, { useState, useEffect } from "react";

import {
    Box,
    Button,
    Checkbox,
    FormControl,
    ListItemText,
    MenuItem,
    OutlinedInput,
    Paper,
    Radio,
    Select,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
} from "@mui/material";
import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";

// const months = [
//     "Jan-24",
//     "Feb-24",
//     "Mar-24",
//     "Apr-24",
//     "May-24",
//     "Jun-24",
//     "Jul-24",
//     "Aug-24",
//     "Sep-24",
//     "Oct-24",
//     "Nov-24",
//     "Dec-24",
// ];

export default function HIVMarketTable({
    activeTab,
    tableData,
    months,
    forecastStartIndex,
    selectedMetric,
    setSelectedMetric,
    availableScenarios = [],
    activeScenario,
    selectedMarket,
    selectedProduct,
    viewMode,
    setViewMode,
}) {
    if (!tableData?.rows?.length) {
        return null;
    }

    // useEffect(() => {
    //     setSelectedRow("");
    // }, [tableData]);

    const { type, rows } = tableData;

    // const months =
    //     tableData?.months || [];

    const isTotalMarketVolume =
        activeTab === "total_market_volume";

    const [selectedRow, setSelectedRow] =
        useState("");

    useEffect(() => {
        setSelectedRow(activeScenario || "");
    }, [activeScenario]);

    const [compareScenario, setCompareScenario] =
        useState([]);


    useEffect(() => {
        setCompareScenario(availableScenarios);
    }, [availableScenarios]);
    // const [selectedMetric, setSelectedMetric] =
    //     useState("market_volume");

    // const scenarioOptions = [
    //     "Top-Bottom",
    //     "Bottom-Top",
    // ];

    const isExpandable =
        type === "hierarchy";

    const [expandedRows, setExpandedRows] =
        useState({});

    const [editable, setEditable] = useState(false);

    const [tableRows, setTableRows] = useState([]);

    const [originalRows, setOriginalRows] = useState([]);

    useEffect(() => {
        if (!tableData?.rows?.length) return;

        const cloned =
            JSON.parse(JSON.stringify(tableData.rows));

        setTableRows(cloned);

        setOriginalRows(
            JSON.parse(JSON.stringify(cloned))
        );
    }, [tableData]);

    const handleCancel = () => {

        setTableRows(
            JSON.parse(JSON.stringify(originalRows))
        );

        setEditable(false);

    };

    const handleCellChange = (
        rowIndex,
        childIndex,
        valueIndex,
        value
    ) => {

        const updated =
            JSON.parse(JSON.stringify(tableRows));

        if (childIndex === null) {

            updated[rowIndex].values[valueIndex] =
                Number(value);

        } else {

            updated[rowIndex]
                .children[childIndex]
                .values[valueIndex] =
                Number(value);

        }

        setTableRows(updated);

    };

    const isHighlightedRow = (row, parentRow = null) => {
        switch (activeTab) {
            case "market_distribution":
                return (
                    row.label?.toLowerCase() ===
                    selectedMarket?.toLowerCase()
                );

            case "product_distribution":
                return (
                    row.label?.toLowerCase() ===
                    selectedProduct?.toLowerCase()
                );

            case "market_product":
                return (
                    parentRow?.label?.toLowerCase() ===
                    selectedMarket?.toLowerCase() &&
                    row.label?.toLowerCase() ===
                    selectedProduct?.toLowerCase()
                );

            case "product_market":
                return (
                    parentRow?.label?.toLowerCase() ===
                    selectedProduct?.toLowerCase() &&
                    row.label?.toLowerCase() ===
                    selectedMarket?.toLowerCase()
                );

            default:
                return false;
        }
    };

    const renderEditableCell = (
        value,
        rowIndex,
        childIndex,
        valueIndex
    ) => {

        if (!editable) {

            return Number(value).toLocaleString();

        }

        return (

            <input

                value={value}

                onChange={(e) =>
                    handleCellChange(
                        rowIndex,
                        childIndex,
                        valueIndex,
                        e.target.value
                    )
                }

                style={{
                    width: "55px",
                    border: "1px solid #93c5fd",
                    borderRadius: "4px",
                    textAlign: "center",
                    background: "#eff6ff",
                    padding: "2px 4px",
                }}

            />

        );

    };

    useEffect(() => {
        setEditable(false);
    }, [activeTab, selectedMetric]);

    useEffect(() => {
        if (!isExpandable) return;

        const expanded = {};

        tableRows.forEach((row) => {
            if (row.children?.length) {
                expanded[row.label] = true;
            }
        });

        setExpandedRows(expanded);
    }, [tableRows, isExpandable]);

    const toggleRow = (label) => {
        setExpandedRows((prev) => ({
            ...prev,
            [label]: !prev[label],
        }));
    };

    const handleExpandAll = () => {
        const expanded = {};

        tableRows.forEach((row) => {
            expanded[row.label] = true;
        });

        setExpandedRows(expanded);
    };

    const handleCollapseAll = () => {
        const collapsed = {};

        tableRows.forEach((row) => {
            collapsed[row.label] = false;
        });

        setExpandedRows(collapsed);
    };

    const metricOptions = [
        {
            label: "Market Volume",
            value: "market_volume",
        },
        {
            label: "Market Share",
            value: "market_share",
        },
    ];

    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        width: "200px",

        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
        },
    };

    const primaryButtonStyle = {
        height: "35px",
        borderRadius: "8px",
        textTransform: "none",
        backgroundColor: "#4F46E5",
    };

    const secondaryButtonStyle = {
        height: "35px",
        borderRadius: "8px",
        textTransform: "none",
    };


    const isOverallFlatRow = (row) =>
        type === "flat" &&
        row.label === "Overall"
    // &&
    // (
    //     activeTab === "market_distribution" ||
    //     activeTab === "product_distribution"
    // );

    const isYearlyView = viewMode === "yearly";

    useEffect(() => {
        if (viewMode === "yearly") {
            setEditable(false);
        }
    }, [viewMode]);

    return (
        <Paper
            sx={{
                mt: 3,
                borderRadius: "12px",
                border: "1px solid #D8DEE8",
                boxShadow: "none",
            }}
        >
            <Box
                sx={{
                    px: 2,
                    py: 2,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 2,
                    borderBottom: "1px solid #E2E8F0",
                }}
            >

                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                    }}
                >

                    <Typography
                        sx={{
                            fontWeight: 700,
                            fontSize: 16,
                        }}
                    >
                        Market Metrics Table
                    </Typography>

                    {rows.some(row => row.children?.length) && (
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

                <Box
                    sx={{
                        display: "flex",
                        gap: 1,
                        alignItems: "center",
                        flexWrap: "wrap",
                    }}
                >

                    {/* <Box
                        sx={{
                            display: "flex",
                            bgcolor: "#E2E8F0",
                            borderRadius: "10px",
                            p: "2px",
                        }}
                    >
                        <Button
                            onClick={() => setViewMode("monthly")}
                            sx={{
                                minWidth: 90,
                                textTransform: "none",
                                borderRadius: "8px",
                                bgcolor:
                                    viewMode === "monthly"
                                        ? "#fff"
                                        : "transparent",
                                color:
                                    viewMode === "monthly"
                                        ? "#4F46E5"
                                        : "#64748B",
                                boxShadow:
                                    viewMode === "monthly"
                                        ? 1
                                        : "none",
                            }}
                        >
                            Monthly
                        </Button>

                        <Button
                            onClick={() => setViewMode("yearly")}
                            sx={{
                                minWidth: 90,
                                textTransform: "none",
                                borderRadius: "8px",
                                bgcolor:
                                    viewMode === "yearly"
                                        ? "#fff"
                                        : "transparent",
                                color:
                                    viewMode === "yearly"
                                        ? "#4F46E5"
                                        : "#64748B",
                                boxShadow:
                                    viewMode === "yearly"
                                        ? 1
                                        : "none",
                            }}
                        >
                            Yearly
                        </Button>
                    </Box> */}

                    {isTotalMarketVolume && (

                        <>


                            <Button
                                variant="contained"
                                sx={primaryButtonStyle}
                                disabled={!selectedRow}
                            >
                                Apply Selected Scenario
                            </Button>

                            <FormControl sx={inputStyle}>
                                <Select
                                    multiple
                                    displayEmpty
                                    value={compareScenario}
                                    onChange={(e) =>
                                        setCompareScenario(
                                            e.target.value
                                        )
                                    }
                                    input={
                                        <OutlinedInput />
                                    }
                                    displayEmpty
                                    renderValue={(selected) => {
                                        if (!selected.length) {
                                            return "Compare Scenarios";
                                        }

                                        if (selected.length === availableScenarios.length) {
                                            return "All Scenarios";
                                        }

                                        return selected.join(", ");
                                    }}
                                >
                                    {availableScenarios.map((option) => (
                                        <MenuItem
                                            key={option}
                                            value={option}
                                        >
                                            <Checkbox
                                                checked={compareScenario.includes(
                                                    option
                                                )}
                                            />

                                            <ListItemText
                                                primary={option}
                                            />
                                        </MenuItem>
                                    )
                                    )}
                                </Select>
                            </FormControl>

                        </>

                    )}

                    <FormControl
                        sx={{
                            ...inputStyle,
                            width: 160,
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

                    {editable && (
                        <Button
                            variant="contained"
                            sx={primaryButtonStyle}
                        // onClick={handleApply}
                        >
                            Apply
                        </Button>
                    )}

                    <Button
                        variant="outlined"
                        sx={secondaryButtonStyle}
                        onClick={() => setEditable(true)}
                        disabled={editable || isYearlyView}
                    >
                        {editable ? "Editing..." : "Edit Changes"}
                    </Button>

                    <Button
                        variant="outlined"
                        sx={secondaryButtonStyle}
                        onClick={handleCancel}
                        disabled={isYearlyView}
                    >
                        Cancel
                    </Button>

                </Box>

            </Box>
            <TableContainer
                sx={{
                    maxHeight: 500,
                    overflow: "auto",
                }}
            >
                <Table stickyHeader size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell
                                sx={{
                                    minWidth: 180,
                                    fontWeight: 700,
                                    background: "#F8FAFC",
                                    position: "sticky",
                                    left: 0,
                                    zIndex: 10,
                                    borderRight: "1px solid #E2E8F0",
                                }}
                            >
                                Category
                            </TableCell>

                            {months.map((month) => (
                                <TableCell
                                    key={month}
                                    align="center"
                                    sx={{
                                        fontWeight: 700,
                                        background: "#F8FAFC",
                                        minWidth: 90,
                                        borderRight: "1px solid #E2E8F0",
                                    }}
                                >
                                    {month}
                                </TableCell>
                            ))}
                        </TableRow>
                    </TableHead>

                    <TableBody>

                        {type === "flat" ? (

                            tableRows.map((row, rowIndex) => {
                                const isOverall = isOverallFlatRow(row);
                                const isHighlighted = isHighlightedRow(row);

                                return (
                                    <TableRow
                                        key={row.label}
                                        hover

                                        sx={{
                                            backgroundColor: isOverall ? "#F8FAFC" : "#FFFFFF",
                                        }}

                                    >
                                        <TableCell
                                            sx={{
                                                position: "sticky",
                                                left: 0,
                                                background:
                                                    isHighlighted
                                                        ? "#fffbeb"
                                                        : isOverall
                                                            ? "#F8FAFC"
                                                            : "#FFFFFF",

                                                fontWeight:
                                                    isHighlighted || isOverall
                                                        ? 700
                                                        : 400,

                                                color:
                                                    isHighlighted
                                                        ? "#f59e0b"
                                                        : "#334155",
                                                borderRight: "1px solid #E2E8F0",

                                            }}
                                        >

                                            <Box
                                                sx={{
                                                    display: "flex",
                                                    alignItems: "center",
                                                    fontWeight: "inherit",
                                                    color: "inherit",
                                                }}
                                            >

                                                {isTotalMarketVolume && (
                                                    <Radio
                                                        size="small"
                                                        checked={selectedRow === row.label}
                                                        onChange={() => setSelectedRow(row.label)}
                                                    />
                                                )}
                                                {row.label}
                                            </Box>

                                        </TableCell>

                                        {row.values.map((value, index) => (

                                            <TableCell
                                                key={index}
                                                align="center"
                                                sx={{
                                                    borderRight: "1px solid #E2E8F0",
                                                    backgroundColor:
                                                        isHighlighted && index >= forecastStartIndex
                                                            ? "#fffbeb"
                                                            : index < forecastStartIndex
                                                                ? "#F1F5F9"
                                                                : "#FFFFFF",

                                                    fontWeight:
                                                        isHighlighted && index >= forecastStartIndex
                                                            ? 700
                                                            : 400,

                                                    color:
                                                        isHighlighted && index >= forecastStartIndex
                                                            ? "#f59e0b"
                                                            : "#334155",
                                                }}
                                            >
                                                {renderEditableCell(
                                                    value,
                                                    rowIndex,
                                                    null,
                                                    index
                                                )}
                                            </TableCell>

                                        ))}

                                    </TableRow>
                                );

                            })

                        ) : (

                            tableRows.map((parent, parentIndex) => {
                                const parentHighlighted = isHighlightedRow(parent);
                                return (

                                    <React.Fragment key={parent.label}>

                                        {/* Parent Row */}

                                        <TableRow
                                            sx={{
                                                background: "#F8FAFC",
                                            }}
                                        >
                                            <TableCell
                                                sx={{
                                                    position: "sticky",
                                                    left: 0,
                                                    background:
                                                        parentHighlighted
                                                            ? "#fffbeb"
                                                            : "#F8FAFC",

                                                    color:
                                                        parentHighlighted
                                                            ? "#f59e0b"
                                                            : "#334155",

                                                    fontWeight: 700,
                                                    borderRight: "1px solid #E2E8F0",
                                                }}
                                            >
                                                <Box
                                                    sx={{
                                                        display: "flex",
                                                        alignItems: "center",
                                                        pl: parent.children?.length ? 0 : "36px",
                                                    }}
                                                >
                                                    {parent.children?.length > 0 && (
                                                        <IconButton
                                                            size="small"
                                                            onClick={() =>
                                                                toggleRow(parent.label)
                                                            }
                                                            sx={{
                                                                mr: 1,
                                                            }}
                                                        >
                                                            {expandedRows[parent.label] ? (
                                                                <KeyboardArrowDownIcon fontSize="small" />
                                                            ) : (
                                                                <KeyboardArrowRightIcon fontSize="small" />
                                                            )}
                                                        </IconButton>
                                                    )}

                                                    {parent.label}
                                                </Box>
                                            </TableCell>


                                            {months.map((_, index) => (
                                                <TableCell
                                                    key={index}
                                                    align="center"
                                                    sx={{
                                                        // backgroundColor:
                                                        //     index < forecastStartIndex
                                                        //         ? "#F1F5F9"
                                                        //         : "#F8FAFC",

                                                        borderRight: "1px solid #E2E8F0",
                                                        backgroundColor:
                                                            parentHighlighted && index >= forecastStartIndex
                                                                ? "#fffbeb"
                                                                : index < forecastStartIndex
                                                                    ? "#F1F5F9"
                                                                    : "#F8FAFC",

                                                        fontWeight:
                                                            parentHighlighted && index >= forecastStartIndex
                                                                ? 700
                                                                : 700,

                                                        color:
                                                            parentHighlighted && index >= forecastStartIndex
                                                                ? "#f59e0b"
                                                                : "#334155",
                                                    }}
                                                >
                                                    {parent.values?.[index] !== undefined
                                                        ? Number(parent.values[index]).toLocaleString()
                                                        : ""}
                                                </TableCell>
                                            ))}

                                        </TableRow>

                                        {/* Children */}

                                        {(!isExpandable ||
                                            expandedRows[parent.label]) &&
                                            parent.children?.map((child, childIndex) => {
                                                const isHighlighted = isHighlightedRow(child, parent);

                                                return (
                                                    <TableRow
                                                        key={child.label}
                                                        hover
                                                    >
                                                        <TableCell
                                                            sx={{
                                                                position: "sticky",
                                                                left: 0,
                                                                // background: isHighlighted
                                                                //     ? "#fffbeb"
                                                                //     : "#fff",

                                                                pl: 5,

                                                                background:
                                                                    isHighlighted
                                                                        ? "#fffbeb"
                                                                        : "#FFFFFF",

                                                                fontWeight:
                                                                    isHighlighted
                                                                        ? 700
                                                                        : 400,

                                                                color:
                                                                    isHighlighted
                                                                        ? "#f59e0b"
                                                                        : "#334155",
                                                                borderRight: "1px solid #E2E8F0",
                                                            }}
                                                        >
                                                            {child.label}
                                                        </TableCell>

                                                        {child.values.map((value, index) => (

                                                            <TableCell
                                                                key={index}
                                                                align="center"
                                                                sx={{
                                                                    borderRight: "1px solid #E2E8F0",
                                                                    backgroundColor:
                                                                        isHighlighted && index >= forecastStartIndex
                                                                            ? "#fffbeb"
                                                                            : index < forecastStartIndex
                                                                                ? "#F1F5F9"
                                                                                : "#FFFFFF",

                                                                    fontWeight:
                                                                        isHighlighted && index >= forecastStartIndex
                                                                            ? 700
                                                                            : 400,

                                                                    color:
                                                                        isHighlighted && index >= forecastStartIndex
                                                                            ? "#f59e0b"
                                                                            : "#334155",
                                                                }}
                                                            >
                                                                {renderEditableCell(
                                                                    value,
                                                                    parentIndex,
                                                                    childIndex,
                                                                    index
                                                                )}
                                                            </TableCell>

                                                        ))}

                                                    </TableRow>
                                                );

                                            })}

                                    </React.Fragment>
                                );

                            })

                        )}

                    </TableBody>
                </Table>
            </TableContainer>
        </Paper>
    );
}