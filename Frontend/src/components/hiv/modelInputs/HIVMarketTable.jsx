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
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
} from "@mui/material";
import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";
// import IconButton from "@mui/material/IconButton";
// import Tooltip from "@mui/material/Tooltip";

import DownloadIcon from "@mui/icons-material/Download";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import ExcelJS from "exceljs";
import { saveAs } from "file-saver";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";

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
    marketAnalysis,
    onEdit,
    onSaveScenario,
    onApplyScenario,
    allScenariosData,
    onUpdateScenario,
    compareScenario,
    setCompareScenario,
    onDeleteScenario
}) {
    if (!tableData?.rows?.length) {
        return null;
    }

    // useEffect(() => {
    //     setSelectedRow("");
    // }, [tableData]);

    // const [compareScenario, setCompareScenario] =
    //     useState([]);


    // const isTmvTab = activeTab === "total_market_volume";

    // const tmvMergedRows = React.useMemo(() => {
    //     if (!isTmvTab) return null;

    //     return compareScenario
    //         .map((scenarioName) => {
    //             const scenarioRow =
    //                 allScenariosData?.[scenarioName]
    //                     ?.market_analysis
    //                     ?.total_market_volume
    //                     ?.[selectedMetric]
    //                     ?.[viewMode]
    //                     ?.table
    //                     ?.rows?.[0];

    //             return scenarioRow || null;
    //         })
    //         .filter(Boolean);
    // }, [isTmvTab, allScenariosData, compareScenario, selectedMetric, viewMode]);

    const appendScenario = (rows, scenarioName) =>
        rows.map((row) => {

            const shouldAppendScenario =
                row.label !== scenarioName;

            return {

                ...row,

                scenario: scenarioName,

                label: shouldAppendScenario
                    ? `${row.label} (${scenarioName})`
                    : row.label,

                children: row.children
                    ? appendScenario(
                        row.children,
                        scenarioName
                    )
                    : undefined,

            };

        });

    const mergedRows = React.useMemo(() => {

        return compareScenario.flatMap(scenarioName => {

            const rows =
                allScenariosData?.[scenarioName]
                    ?.market_analysis
                    ?.[activeTab]
                    ?.[selectedMetric]
                    ?.[viewMode]
                    ?.table
                    ?.rows;

            if (!rows?.length) {
                return [];
            }

            return appendScenario(rows, scenarioName);

        });

    }, [
        compareScenario,
        allScenariosData,
        activeTab,
        selectedMetric,
        viewMode,
    ]);


    // const effectiveRows = isTmvTab && tmvMergedRows?.length ? tmvMergedRows : tableData.rows;
    const effectiveRows =
        mergedRows.length
            ? mergedRows
            : tableData.rows;
    const { type } = tableData;
    const rows = effectiveRows;

    // const months =
    //     tableData?.months || [];

    const isTotalMarketVolume =
        activeTab === "total_market_volume";

    const [selectedRow, setSelectedRow] =
        useState("");

    const [deleteDialogOpen, setDeleteDialogOpen] =
        useState(false);

    const [scenarioToDelete, setScenarioToDelete] =
        useState("");

    useEffect(() => {
        setSelectedRow(activeScenario || "");
    }, [activeScenario]);

    useEffect(() => {
        if (activeTab === "total_market_volume") {
            setSelectedMetric("market_volume");
        }
    }, [activeTab, setSelectedMetric]);


    // useEffect(() => {
    //     setCompareScenario(availableScenarios);
    // }, [availableScenarios]);

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

    const [openSaveScenario, setOpenSaveScenario] = useState(false);

    const [scenarioName, setScenarioName] = useState("");

    const [editedRows, setEditedRows] = useState([]);

    useEffect(() => {

        const sourceRows =
            mergedRows.length
                ? mergedRows
                : tableData.rows;

        if (!sourceRows?.length) return;

        const cloned = JSON.parse(JSON.stringify(sourceRows));

        setTableRows(cloned);
        setOriginalRows(JSON.parse(JSON.stringify(cloned)));
        setEditedRows([]);

    }, [
        mergedRows,
        tableData,
    ]);

    const handleCancel = () => {

        setTableRows(
            JSON.parse(JSON.stringify(originalRows))
        );

        setEditable(false);

    };

    const removeScenario = (rows) =>
        rows.map(row => ({

            ...row,

            label: row.label.split(" (")[0],

            scenario: undefined,

            children: row.children
                ? removeScenario(row.children)
                : undefined,

        }));

    const handleRefresh = async () => {

        const updatedMarketAnalysis =
            JSON.parse(JSON.stringify(marketAnalysis));

        const activeRows =
            tableRows.filter(
                row =>
                    row.scenario === activeScenario
            );

        updatedMarketAnalysis
        [activeTab]
        [selectedMetric]
        [viewMode]
            .table
            .rows =
            removeScenario(activeRows);

        try {

            await onEdit(
                updatedMarketAnalysis,
                editedRows
            );

            setEditable(false);

        }
        catch (err) {

            console.error(
                "Edit failed",
                err
            );

        }

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

        const editedLabel =
            (
                childIndex === null
                    ? updated[rowIndex].label
                    : updated[rowIndex].children[childIndex].label
            ).split(" (")[0];

        setEditedRows((prev) =>
            prev.includes(editedLabel)
                ? prev
                : [...prev, editedLabel]
        );

    };

    const isHighlightedRow = (row, parentRow = null) => {

        const rowLabel =
            row.label.split(" (")[0];

        const parentLabel =
            parentRow?.label
                ?.split(" (")[0];

        switch (activeTab) {

            case "market_distribution":

                return (
                    rowLabel.toLowerCase() ===
                    selectedMarket?.toLowerCase()
                );

            case "product_distribution":

                return (
                    rowLabel.toLowerCase() ===
                    selectedProduct?.toLowerCase()
                );

            case "market_product":

                return (

                    parentLabel?.toLowerCase() ===
                    selectedMarket?.toLowerCase()

                    &&

                    rowLabel.toLowerCase() ===
                    selectedProduct?.toLowerCase()

                );

            case "product_market":

                return (

                    parentLabel?.toLowerCase() ===
                    selectedProduct?.toLowerCase()

                    &&

                    rowLabel.toLowerCase() ===
                    selectedMarket?.toLowerCase()

                );

            default:

                return false;

        }

    };

    const canEditCell = (row, isChild = false) => {
        if (!editable) return false;

        const originalLabel =
            row.label.split(" (")[0];

        if (row.scenario !== activeScenario) {
            return false;
        }

        switch (activeTab) {

            case "market_distribution":

                return originalLabel !== "Overall";

            case "product_distribution":

                return originalLabel !== "Overall";

            case "market_product":

                return isChild;

            case "product_market":

                return isChild;

            case "total_market_volume":

                return true;

        }
    };

    const renderEditableCell = (
        value,
        rowIndex,
        childIndex,
        valueIndex
    ) => {

        if (!editable) {

            return formatCellValue(value);
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

    const formatCellValue = (value) => {
        if (value === null || value === undefined || value === "") {
            return "";
        }

        if (editable) {
            return value;
        }

        if (selectedMetric === "market_share") {
            return `${value}%`;
        }

        return Number(value).toLocaleString();
    };

    useEffect(() => {
        setEditable(false);
    }, [activeTab, selectedMetric]);

    useEffect(() => {
        if (!isExpandable) return;

        const expanded = {};

        tableRows.forEach((row) => {
            if (row.children?.length) {
                expanded[row.label] = false;
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
        row.label.startsWith("Overall");
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

    // const handleEditClick = () => {
    //     if (selectedMetric !== "market_share") return;

    //     setEditable(true);
    // };

    const handleEditClick = () => {
        const canEdit =
            isTotalMarketVolume ||
            selectedMetric === "market_share";

        if (!canEdit) return;

        setEditable(true);
    };

    const handleDownloadExcel = async () => {

        if (!tableData?.rows?.length) return;

        const workbook = new ExcelJS.Workbook();

        const sheetName = {
            total_market_volume: "Total Market Volume",
            market_distribution: "Market Distribution",
            product_distribution: "Product Distribution",
            market_product: "Market Product",
            product_market: "Product Market",
        }[activeTab];

        const worksheet =
            workbook.addWorksheet(sheetName);

        // Header
        worksheet.addRow(["Scenario", activeScenario]);
        worksheet.addRow(["Market", selectedMarket]);
        worksheet.addRow(["Product", selectedProduct]);
        worksheet.addRow([
            "Metric",
            selectedMetric === "market_share"
                ? "Market Share"
                : "Market Volume",
        ]);
        worksheet.addRow([
            "View",
            viewMode === "monthly"
                ? "Monthly"
                : "Yearly",
        ]);

        worksheet.addRow([]);

        const headerRowNumber =
            worksheet.rowCount + 1;

        worksheet.addRow([
            "Label",
            ...months,
        ]);

        tableRows.forEach((row) => {

            const excelRow =
                worksheet.addRow([
                    row.label,
                    ...(row.values || []).map(value =>
                        selectedMetric === "market_share"
                            ? `${value}%`
                            : Number(value).toLocaleString("en-US")
                    ),
                ]);

            if (
                row.children?.length ||
                row.label === "Overall"
            ) {
                excelRow.font = {
                    bold: true,
                };
            }

            row.children?.forEach(child => {

                worksheet.addRow([
                    "    " + child.label,
                    ...(child.values || []).map(value =>
                        selectedMetric === "market_share"
                            ? `${value}%`
                            : Number(value).toLocaleString("en-US")
                    ),
                ]);

            });

        });

        worksheet.getRow(headerRowNumber).font = {
            bold: true,
        };

        worksheet.eachRow((row) => {

            row.eachCell((cell) => {

                cell.border = {
                    top: { style: "thin" },
                    left: { style: "thin" },
                    right: { style: "thin" },
                    bottom: { style: "thin" },
                };

                cell.alignment = {
                    vertical: "middle",
                    horizontal:
                        cell.col === 1
                            ? "left"
                            : "center",
                };

            });

        });

        worksheet.getColumn(1).width = 30;

        for (let i = 2; i <= months.length + 1; i++) {
            worksheet.getColumn(i).width = 14;
        }

        const buffer =
            await workbook.xlsx.writeBuffer();

        saveAs(
            new Blob([buffer]),
            `${sheetName}_${viewMode}.xlsx`
        );

    };

    const handleDeleteClick = (scenario) => {
        setScenarioToDelete(scenario);
        setDeleteDialogOpen(true);
    };

    const confirmDelete = async () => {
        await onDeleteScenario(scenarioToDelete);

        setDeleteDialogOpen(false);
        setScenarioToDelete("");
    };

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
                        gap: 2,
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

                    <Button
                        variant="contained"
                        sx={primaryButtonStyle}
                        onClick={() => setOpenSaveScenario(true)}
                    >
                        Save Scenario
                    </Button>

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

                    <Tooltip title="Download Table">
                        <IconButton
                            size="small"
                            onClick={handleDownloadExcel}
                        >
                            <DownloadIcon />
                        </IconButton>
                    </Tooltip>

                    <Box
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
                                minWidth: 80,
                                height: 30,
                                px: 1.5,
                                py: 0.25,
                                textTransform: "none",
                                borderRadius: "8px",
                                bgcolor: viewMode === "monthly" ? "#fff" : "transparent",
                                color: viewMode === "monthly" ? "#4F46E5" : "#64748B",
                                boxShadow: viewMode === "monthly" ? 1 : "none",
                            }}
                        >

                            Monthly
                        </Button>


                        <Button
                            onClick={() => setViewMode("yearly")}
                            sx={{
                                minWidth: 80,
                                height: 30,
                                px: 1.5,
                                py: 0.25,
                                textTransform: "none",
                                borderRadius: "8px",
                                bgcolor: viewMode === "yearly" ? "#fff" : "transparent",
                                color: viewMode === "yearly" ? "#4F46E5" : "#64748B",
                                boxShadow: viewMode === "yearly" ? 1 : "none",
                            }}
                        >

                            Yearly
                        </Button>
                    </Box>

                    {isTotalMarketVolume && (
                        // <>
                        <Button
                            variant="contained"
                            sx={primaryButtonStyle}
                            disabled={!selectedRow}
                            onClick={async () => {
                                await onApplyScenario(selectedRow);
                            }}
                        >
                            Apply Selected Scenario
                        </Button>

                    )}



                    <FormControl sx={inputStyle}>
                        <Select
                            multiple
                            displayEmpty
                            value={compareScenario}
                            onChange={(e) => {
                                let value = e.target.value;

                                if (!value.includes(activeScenario)) {
                                    value = [...value, activeScenario];
                                }

                                setCompareScenario(value);
                            }}
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
                            {availableScenarios.map((option) => {
                                const isActive = option === activeScenario;

                                return (
                                    <MenuItem
                                        key={option}
                                        value={option}
                                        disabled={isActive}
                                    >
                                        <Checkbox
                                            checked={compareScenario.includes(option)}
                                            disabled={isActive}
                                        />

                                        <ListItemText
                                            primary={
                                                isActive
                                                    ? `${option} (Active)`
                                                    : option
                                            }
                                        />
                                    </MenuItem>
                                );
                            })}
                        </Select>
                    </FormControl>

                    {/* </> */}

                    {!isTotalMarketVolume && (
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
                    )}

                    {/* <Button
                        variant="contained"
                        sx={primaryButtonStyle}
                        disabled={editable}
                    // onClick={handleSave} // your save handler
                    >
                        Save
                    </Button> */}

                    <Button
                        variant="contained"
                        sx={primaryButtonStyle}
                        disabled={editable}
                        onClick={async () => {
                            if (activeScenario === "Base") {
                                setOpenSaveScenario(true);
                            } else {
                                await onUpdateScenario();
                            }
                        }}
                    >
                        Save
                    </Button>

                    {/* {!isTotalMarketVolume && ( */}

                    <Button
                        variant="outlined"
                        sx={secondaryButtonStyle}
                        onClick={handleEditClick}
                        disabled={
                            editable ||
                            viewMode === "yearly" ||
                            (
                                !isTotalMarketVolume &&
                                selectedMetric !== "market_share"
                            )
                        }
                    >
                        {/* {editable ? "Editing..." : "Edit Changes"} */}
                        Edit changes
                    </Button>

                    {/* )} */}

                    {editable && (
                        <>
                            <Button
                                variant="contained"
                                sx={primaryButtonStyle}
                                onClick={handleRefresh}
                            >
                                Refresh
                            </Button>

                            <Button
                                variant="outlined"
                                sx={secondaryButtonStyle}
                                onClick={handleCancel}
                                disabled={isYearlyView}
                            >
                                Cancel
                            </Button>
                        </>
                    )}
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

                                                fontWeight: isOverall ? 700 : 400,

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
                                                    justifyContent: "space-between",
                                                    width: "100%",
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
                                                            checked={selectedRow === row.scenario}
                                                            onChange={() => setSelectedRow(row.scenario)}
                                                        />
                                                    )}
                                                    {row.label}
                                                </Box>
                                                {row.label !== "Base" && (
                                                    <Tooltip title="Delete Scenario">
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => handleDeleteClick(row.label)}
                                                        >
                                                            <DeleteOutlineIcon
                                                                fontSize="small"
                                                                color="error"
                                                            />
                                                        </IconButton>
                                                    </Tooltip>
                                                )}
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

                                                    fontWeight: isOverall ? 700 : 400,

                                                    color:
                                                        isHighlighted && index >= forecastStartIndex
                                                            ? "#f59e0b"
                                                            : "#334155",
                                                }}
                                            >
                                                {canEditCell(row)
                                                    ? renderEditableCell(
                                                        value,
                                                        rowIndex,
                                                        null,
                                                        index
                                                    )
                                                    : formatCellValue(value)}
                                            </TableCell>

                                        ))}

                                    </TableRow>
                                );

                            })

                        ) : (

                            tableRows.map((parent, parentIndex) => {
                                const parentHighlighted = isHighlightedRow(parent);

                                const isOverallRow =
                                    ["market_distribution", "product_distribution"].includes(activeTab) &&
                                    parent.label.split(" (")[0].trim() === "Overall";

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

                                                    fontWeight:
                                                        (activeTab === "market_distribution" ||
                                                            activeTab === "product_distribution")
                                                            ? (isOverallRow ? 700 : 400)
                                                            : (parentHighlighted ? 700 : 700),

                                                    borderRight: "1px solid #E2E8F0",
                                                }}
                                            >
                                                <Box
                                                    sx={{
                                                        display: "flex",
                                                        alignItems: "center",
                                                        pl: parent.children?.length ? 0 : 0.5,
                                                    }}
                                                >
                                                    {parent.children?.length > 0 && (
                                                        <IconButton
                                                            size="small"
                                                            onClick={() =>
                                                                toggleRow(parent.label)
                                                            }
                                                            sx={{
                                                                mr: 0.25,      // instead of 1
                                                                p: 0.5,       // smaller clickable area
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
                                                            (activeTab === "market_distribution" ||
                                                                activeTab === "product_distribution")
                                                                ? (isOverallRow ? 700 : 400)
                                                                : (parentHighlighted ? 700 : 700),

                                                        color:
                                                            parentHighlighted && index >= forecastStartIndex
                                                                ? "#f59e0b"
                                                                : "#334155",
                                                    }}
                                                >
                                                    {parent.values?.[index] !== undefined
                                                        ? canEditCell(parent)
                                                            ? renderEditableCell(
                                                                parent.values[index],
                                                                parentIndex,
                                                                null,
                                                                index
                                                            )
                                                            : formatCellValue(parent.values[index])
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

                                                                fontWeight: 400,

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
                                                                    pl: 2,
                                                                }}
                                                            >
                                                                {child.label}
                                                            </Box>
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

                                                                    fontWeight: 400,
                                                                    color:
                                                                        isHighlighted && index >= forecastStartIndex
                                                                            ? "#f59e0b"
                                                                            : "#334155",
                                                                }}
                                                            >
                                                                {canEditCell(child, true)
                                                                    ? renderEditableCell(
                                                                        value,
                                                                        parentIndex,
                                                                        childIndex,
                                                                        index
                                                                    )
                                                                    : formatCellValue(value)}
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
            <Dialog
                open={openSaveScenario}
                onClose={() => setOpenSaveScenario(false)}
                maxWidth="xs"
                fullWidth
                PaperProps={{ sx: { borderRadius: "12px" } }}
            >
                <DialogTitle sx={{ fontWeight: 700, fontSize: "16px", color: "#0f172a", pb: 1 }}>
                    Save Scenario
                </DialogTitle>

                <DialogContent>
                    <Typography sx={{ fontSize: "13px", color: "#64748b", mb: 2 }}>
                        Enter a name for this scenario.
                    </Typography>
                    <TextField
                        autoFocus
                        fullWidth
                        label="Scenario Name"
                        placeholder="Enter scenario name"
                        value={scenarioName}
                        onChange={(e) =>
                            setScenarioName(e.target.value)
                        }
                        variant="outlined"
                        sx={{ "& .MuiOutlinedInput-root": { borderRadius: "8px" } }}
                    />
                </DialogContent>

                <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}>
                    <Button
                        variant="outlined"
                        onClick={() => {
                            setOpenSaveScenario(false);
                            setScenarioName("");
                        }}
                        sx={{ textTransform: "none", borderRadius: "8px", color: "#64748b", borderColor: "#e2e8f0" }}
                    >
                        Cancel
                    </Button>

                    <Button
                        variant="contained"
                        disabled={!scenarioName.trim()}
                        onClick={async () => {
                            await onSaveScenario(scenarioName);

                            setOpenSaveScenario(false);
                            setScenarioName("");
                        }}
                        sx={{ textTransform: "none", borderRadius: "8px", backgroundColor: "#4F46E5" }}
                    >
                        Save
                    </Button>
                </DialogActions>
            </Dialog>
            <Dialog
                open={deleteDialogOpen}
                onClose={() => setDeleteDialogOpen(false)}
            >
                <DialogTitle sx={{ fontWeight: 700, fontSize: "18px", color: "#0f172a", pb: 1 }}>
                    Delete Scenario
                </DialogTitle>

                <DialogContent>
                    <Typography sx={{ fontSize: "16px", color: "#64748b", mb: 2 }}>
                        Are you sure you want to delete
                        <b> {scenarioToDelete}</b>?
                    </Typography>
                </DialogContent>

                <DialogActions>
                    <Button
                        variant="outlined"
                        onClick={() =>
                            setDeleteDialogOpen(false)
                        }
                        sx={{ textTransform: "none", borderRadius: "8px", color: "#64748b", borderColor: "#e2e8f0" }}
                    >
                        Cancel
                    </Button>

                    <Button
                        color="error"
                        variant="contained"
                        onClick={confirmDelete}
                        sx={{ textTransform: "none", borderRadius: "8px" }}
                    >
                        Delete
                    </Button>
                </DialogActions>
            </Dialog>
        </Paper>
    );
}