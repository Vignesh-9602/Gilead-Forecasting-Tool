​import React, { useContext, useEffect, useState } from "react";

import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    Button,
    Tabs,
    Tab,
    TextField,
    Menu,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Checkbox,
    ListItemText,
    IconButton,
    Switch
} from "@mui/material";

import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

import dayjs from "dayjs";

import MoreVertIcon from "@mui/icons-material/MoreVert";
import CloseIcon from "@mui/icons-material/Close";

import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";

import { GlobalContext } from "../../../context/Provider";
import { marketEventMock } from "./MEMockData.js";
import HIVImpactCurveChart from "./MarketEventChart";
import HIVImpactCurveTable from "./MarketEventTable";

const globalConfigDateLocaleText = {
    fieldMonthPlaceholder: () => "MM",
    fieldYearPlaceholder: () => "YYYY",
};

export default function HIVMarketEvent() {

    const { favState } = useContext(GlobalContext);

    const therapyArea =
        favState?.selectedTherapyArea || "HIV Treatment";

    const [availableMonths, setAvailableMonths] = useState([]);
    const [availableScenarios, setAvailableScenarios] = useState([]);

    const [eventTabsData, setEventTabsData] = useState({});

    const [scenarioName, setScenarioName] = useState("");

    const [selectedPayers, setSelectedPayers] = useState([]);
    const [selectedProducts, setSelectedProducts] = useState([]);

    const [fromDate, setFromDate] = useState("");
    const [toDate, setToDate] = useState("");

    const [activeTab, setActiveTab] =
        useState("market_event");

    const isMarketEvent =
        activeTab === "market_event";

    const isProductEvent =
        activeTab === "product_event";

    const isOverallEvent =
        activeTab === "overall_event";

    const [eventRows, setEventRows] =
        useState([]);

    const [selectedMetric, setSelectedMetric] =
        useState("market_volume");

    const [selectedView, setSelectedView] =
        useState("monthly");

    useEffect(() => {

        if (!currentConfig) return;

        const rows = currentConfig.rows || [];

        setEventRows(
            rows.length
                ? rows
                : [createEmptyRow(currentConfig)]
        );

    }, [activeTab, eventTabsData]);

    const currentConfig =
        eventTabsData?.[activeTab]
            ?.impact_curve_configuration || {};

    const currentMetricData =
        eventTabsData?.[activeTab]
            ?.metrics_views?.[
        selectedMetric
        ]?.[
        selectedView
        ] ||
        eventTabsData?.[activeTab]
            ?.metrics_views?.[
        selectedMetric
        ]?.monthly || {};

    const createEmptyRow = (config) => ({


        id: Date.now(),

        event_name: "",

        products: [],

        markets: [],

        impacted_items: [],

        start_date:
            config.forecast_start_date || "",

        peak_percent: "",

        months: "",

        curve_type:
            config.curve_types?.[0] || "",

        factor: "",

        enable_coverage: false,

        coverage_peak_percent: "",

        coverage_curve: "",

        coverage_factor: "",

        coverage_peak_months: "",

    });

    const [menuAnchorEl, setMenuAnchorEl] =
        useState(null);

    const [selectedRowIndex, setSelectedRowIndex] =
        useState(null);

    const [openDeleteDialog, setOpenDeleteDialog] =
        useState(false);

    const [openImpactDialog, setOpenImpactDialog] =
        useState(false);

    const [selectedImpactRowIndex, setSelectedImpactRowIndex] =
        useState(null);

    useEffect(() => {
        fetchFilters();
    }, []);

    const fetchFilters = () => {

        const response = marketEventMock;

        setAvailableScenarios(
            response.available_scenarios ||
            response.scenario_names ||
            []
        );

        setAvailableMonths(
            response.available_months
        );

        const filter = response.selected_filter || {};

        setScenarioName(filter.scenario_name || "Base");

        setSelectedPayers(
            Array.isArray(filter.markets)
                ? filter.markets
                : Array.isArray(filter.payers)
                    ? filter.payers
                    : filter.market
                        ? [filter.market]
                        : filter.payer
                            ? [filter.payer]
                            : []
        );

        setSelectedProducts(
            Array.isArray(filter.products)
                ? filter.products
                : filter.product
                    ? [filter.product]
                    : []
        );

        setFromDate(filter.start_date);

        setToDate(filter.end_date);

        setEventTabsData(response.event_tabs || {});
    };

    const handleApplyFilter = () => {

        const payload = {
            ta_name: therapyArea,

            scenario_name: scenarioName,

            payers: selectedPayers,

            markets: selectedPayers,

            products: selectedProducts,

            start_date: fromDate,

            end_date: toDate,
        };

        console.log(payload);
        const rows = currentConfig.rows || [];

        setEventRows(
            rows.length
                ? rows
                : [createEmptyRow(currentConfig)]
        );
    };

    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "170px",
        maxWidth: "260px",

        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
            overflow: "hidden",
        },
    };

    const labelStyle = {
        mb: 1,
        fontSize: "14px",
        fontWeight: 700,
        color: "#64748b",
    };

    const EVENT_TABS = [
        {
            label: "Payer Event",
            value: "market_event",
        },
        {
            label: "Product Event",
            value: "product_event",
        },
        {
            label: "Overall Event",
            value: "overall_event",
        },
    ];



    const handleAddNewEvent = () => {
        setEventRows((prev) => [
            ...prev,
            createEmptyRow(currentConfig)
        ]);
    };

    const handleDuplicateRow = () => {

        if (selectedRowIndex == null)
            return;

        const row = eventRows[selectedRowIndex];

        const updated = [...eventRows];

        updated.splice(
            selectedRowIndex + 1,
            0,
            {
                ...row,
                products: [...row.products],
                markets: [...row.markets],
                impacted_items: [
                    ...row.impacted_items,
                ],
            }
        );

        setEventRows(updated);

        setMenuAnchorEl(null);
    };

    const handleDeleteRow = () => {

        setEventRows((prev) =>
            prev.filter(
                (_, index) =>
                    index !== selectedRowIndex
            )
        );

        setOpenDeleteDialog(false);

        setMenuAnchorEl(null);
    };

    const handleOpenMenu = (
        event,
        index
    ) => {

        setMenuAnchorEl(
            event.currentTarget
        );

        setSelectedRowIndex(index);

    };

    const handleCloseMenu = () => {

        setMenuAnchorEl(null);

    };

    const handleOpenImpactDialog = (
        index
    ) => {

        setSelectedImpactRowIndex(index);

        setOpenImpactDialog(true);

    };

    const handleCloseImpactDialog = () => {

        setOpenImpactDialog(false);

    };

    const handleRowChange = (
        index,
        field,
        value
    ) => {

        const updated = [...eventRows];

        updated[index] = {
            ...updated[index],
            [field]: value,
        };

        // Clear coverage values when Coverage is turned OFF
        if (field === "enable_coverage" && !value) {
            updated[index].coverage_peak_percent = "";
            updated[index].coverage_curve = "";
            updated[index].coverage_factor = "";
            updated[index].coverage_peak_months = "";
        }

        setEventRows(updated);

    };

    const handleImpactSelection = (
        value
    ) => {

        const updated = [...eventRows];

        updated[
            selectedImpactRowIndex
        ].impacted_items = value;

        setEventRows(updated);

    };

    const tableInputStyle = {
        borderRadius: "8px",

        "& .MuiOutlinedInput-root": {
            height: "32px",
            borderRadius: "6px",
            backgroundColor: "#fff",
            fontSize: "13px",
        },
    };

    const tableSelectStyle = {
        "& .MuiOutlinedInput-root": {
            height: "32px",
            borderRadius: "6px",
            backgroundColor: "#fff",
            fontSize: "13px",
            paddingRight: "32px",
        },

        "& .MuiSelect-select": {
            display: "flex",
            alignItems: "center",
            padding: "6px 12px",
            minHeight: "unset !important",
        },

        "& .MuiSelect-icon": {
            color: "#64748b",
            right: 8,
            fontSize: 22,
        },
    };

    const menuProps = {
        PaperProps: {
            sx: {
                maxHeight: 280,
                borderRadius: "8px",

                "& .MuiMenuItem-root": {
                    minHeight: 34,
                    fontSize: "13px",
                },
            },
        },
    };

    const getOptionValue = (option) =>
        typeof option === "string"
            ? option
            : option.value || option.name || "";

    const getOptionLabel = (option) =>
        typeof option === "string"
            ? option
            : option.label || option.name || option.value || "";

    const findOption = (options, value) =>
        (options || []).find((option) =>
            typeof option === "string"
                ? option === value
                : option.value === value || option.name === value,
        );

    const renderOptionValue = (selected, options, placeholder = "Select") => {
        if (!selected || (Array.isArray(selected) && selected.length === 0)) {
            return placeholder;
        }

        if (Array.isArray(selected)) {
            return selected
                .map((item) => {
                    const found = findOption(options, item);
                    return found ? getOptionLabel(found) : String(item);
                })
                .join(", ");
        }

        const found = findOption(options, selected);
        return found ? getOptionLabel(found) : String(selected);
    };

    const headerColumns = isOverallEvent
        ? "0.9fr 0.45fr 0.35fr 0.35fr 0.45fr 0.3fr 0.3fr 0.45fr 0.45fr 40px"
        : "0.8fr 0.6fr 0.55fr 0.65fr 0.45fr 0.35fr 0.35fr 0.45fr 0.3fr 0.3fr 0.3fr 0.3fr 0.45fr 0.45fr 40px";

    const headers = isOverallEvent
        ? [
            "Overall Event",
            "Start Date",
            "Peak %",
            "Months",
            "Curve",
            "Factor",
            "Coverage",
            "Coverage Peak %",
            "Coverage Peak Months",
            "",
        ]
        : [
            isMarketEvent ? "Payer Event" : "Product Event",
            "Products",
            "Payers",
            isMarketEvent
                ? "Impacted Payers"
                : "Impacted Products",
            "Start Date",
            "Peak %",
            "Months",
            "Curve",
            "Factor",
            "Coverage",
            "Coverage Peak %",
            "Coverage Curve",
            "Coverage Factor",
            "Coverage Peak Months",
            "",
        ];

    return (

        <Box sx={{ p: 3 }}>

            <Paper
                sx={{
                    p: 3,
                    borderRadius: "16px",
                    border: "1px solid #D8DEE8",
                    boxShadow: "none",
                }}
            >

                <Box
                    sx={{
                        display: "flex",
                        gap: 3,
                        flexWrap: "wrap",
                        alignItems: "end",
                    }}
                >

                    {/* THERAPY AREA */}

                    <Box>

                        <Typography sx={labelStyle}>
                            THERAPEUTIC AREA
                        </Typography>

                        <Box
                            sx={{
                                height: 35,
                                px: 2,
                                display: "flex",
                                alignItems: "center",
                                gap: 1,
                                border: "1px solid #D8DEE8",
                                borderRadius: "8px",
                                backgroundColor: "#d7dde6",
                                minWidth: "170px",
                            }}
                        >

                            <Box
                                sx={{
                                    width: 8,
                                    height: 8,
                                    borderRadius: "50%",
                                    backgroundColor: "#22c55e",
                                }}
                            />

                            <Typography>
                                {therapyArea}
                            </Typography>

                        </Box>

                    </Box>

                    {/* Scenario */}

                    <Box>

                        <Typography sx={labelStyle}>
                            SCENARIO NAME
                        </Typography>

                        <FormControl sx={inputStyle}>

                            <Select
                                value={scenarioName}
                                onChange={(e) =>
                                    setScenarioName(
                                        e.target.value
                                    )
                                }
                            >

                                {availableScenarios.map((item) => (

                                    <MenuItem
                                        key={item}
                                        value={item}
                                    >
                                        {item}
                                    </MenuItem>

                                ))}

                            </Select>

                        </FormControl>

                    </Box>

                    {/* From */}

                    <Box>

                        <Typography sx={labelStyle}>
                            FROM DATE
                        </Typography>

                        <LocalizationProvider
                            dateAdapter={AdapterDayjs}
                            localeText={
                                globalConfigDateLocaleText
                            }
                        >

                            <FormControl sx={inputStyle}>

                                <Select
                                    value={fromDate}
                                    onChange={(e) =>
                                        setFromDate(
                                            e.target.value
                                        )
                                    }
                                     MenuProps={{
                                        PaperProps: {
                                            sx: {
                                                maxHeight: 300,
                                                width: 130,
                                                "& .MuiMenuItem-root": {
                                                    minHeight: 32,
                                                    fontSize: "15px",
                                                    py: 0.5,
                                                },
                                            },
                                        },
                                    }}
                                    renderValue={(selected) =>
                                        dayjs(selected).format(
                                            "MMM YY"
                                        )
                                    }
                                >

                                    {availableMonths.map((month) => (

                                        <MenuItem
                                            key={month}
                                            value={month}
                                        >
                                            {dayjs(month).format(
                                                "MMM YY"
                                            )}
                                        </MenuItem>

                                    ))}

                                </Select>

                            </FormControl>

                        </LocalizationProvider>

                    </Box>

                    {/* To */}

                    <Box>

                        <Typography sx={labelStyle}>
                            TO DATE
                        </Typography>

                        <LocalizationProvider
                            dateAdapter={AdapterDayjs}
                            localeText={
                                globalConfigDateLocaleText
                            }
                        >

                            <FormControl sx={inputStyle}>

                                <Select
                                    value={toDate}
                                    onChange={(e) =>
                                        setToDate(
                                            e.target.value
                                        )
                                    }
                                     MenuProps={{
                                        PaperProps: {
                                            sx: {
                                                maxHeight: 300,
                                                width: 130,
                                                "& .MuiMenuItem-root": {
                                                    minHeight: 32,
                                                    fontSize: "15px",
                                                    py: 0.5,
                                                },
                                            },
                                        },
                                    }}
                                    renderValue={(selected) =>
                                        dayjs(selected).format(
                                            "MMM YY"
                                        )
                                    }
                                >

                                    {availableMonths
                                        .filter((m) =>
                                            dayjs(m).isAfter(
                                                fromDate
                                            ) ||
                                            dayjs(m).isSame(
                                                fromDate
                                            )
                                        )
                                        .map((month) => (

                                            <MenuItem
                                                key={month}
                                                value={month}
                                            >
                                                {dayjs(month).format(
                                                    "MMM YY"
                                                )}
                                            </MenuItem>

                                        ))}

                                </Select>

                            </FormControl>

                        </LocalizationProvider>

                    </Box>

                    {/* Payer */}

                    <Box>

                        <Typography sx={labelStyle}>
                            PAYER FILTER
                        </Typography>

                        <FormControl sx={inputStyle}>

                            <Select
                                multiple
                                displayEmpty
                                value={selectedPayers}
                                onChange={(e) => {

                                    const value =
                                        e.target.value;

                                    if (
                                        value.includes(
                                            "SELECT_ALL"
                                        )
                                    ) {

                                        if (
                                            selectedPayers.length ===
                                            (currentConfig.markets || []).length
                                        ) {

                                            setSelectedPayers([]);

                                        } else {

                                            setSelectedPayers(
                                                currentConfig.markets || []
                                            );

                                        }

                                    } else {

                                        setSelectedPayers(
                                            value
                                        );

                                    }

                                }}
                                renderValue={(selected) => (
                                    <Box
                                        sx={{
                                            display: "inline-block",
                                            maxWidth: "170px",
                                            whiteSpace: "nowrap",
                                            overflow: "hidden",
                                            textOverflow: "ellipsis",
                                            verticalAlign: "middle",
                                        }}
                                    >
                                        {renderOptionValue(
                                            selected,
                                            currentConfig.markets || [],
                                            "Select"
                                        )}
                                    </Box>
                                )}
                            >

                                <MenuItem value="SELECT_ALL">

                                    <Checkbox
                                        checked={
                                            selectedPayers.length ===
                                            (currentConfig.markets || []).length
                                        }
                                        indeterminate={
                                            selectedPayers.length > 0 &&
                                            selectedPayers.length <
                                            (currentConfig.markets || []).length
                                        }
                                    />

                                    <ListItemText
                                        primary="Select All"
                                    />

                                </MenuItem>

                                {(currentConfig.markets || []).map((item) => {
                                    const optionValue = getOptionValue(item);
                                    const optionLabel = getOptionLabel(item);
                                    return (
                                        <MenuItem
                                            key={optionValue}
                                            value={optionValue}
                                        >
                                            <Checkbox
                                                checked={selectedPayers.includes(
                                                    optionValue
                                                )}
                                            />

                                            <ListItemText
                                                primary={optionLabel}
                                            />
                                        </MenuItem>
                                    );
                                })}

                            </Select>

                        </FormControl>

                    </Box>

                    {/* Product */}

                    <Box>

                        <Typography sx={labelStyle}>
                            PRODUCT FILTER
                        </Typography>

                        <FormControl sx={inputStyle}>

                            <Select
                                multiple
                                value={selectedProducts}
                                onChange={(e) => {

                                    const value =
                                        e.target.value;

                                    if (
                                        value.includes(
                                            "SELECT_ALL"
                                        )
                                    ) {

                                        if (
                                            selectedProducts.length ===
                                            (currentConfig.products || []).length
                                        ) {

                                            setSelectedProducts(
                                                []
                                            );

                                        } else {

                                            setSelectedProducts(
                                                currentConfig.products || []
                                            );

                                        }

                                    } else {

                                        setSelectedProducts(
                                            value
                                        );

                                    }

                                }}
                                renderValue={(selected) => (
                                    <Box
                                        sx={{
                                            display: "inline-block",
                                            maxWidth: "170px",
                                            whiteSpace: "nowrap",
                                            overflow: "hidden",
                                            textOverflow: "ellipsis",
                                            verticalAlign: "middle",
                                        }}
                                    >
                                        {renderOptionValue(
                                            selected,
                                            currentConfig.products || [],
                                            "Select"
                                        )}
                                    </Box>
                                )}
                            >

                                <MenuItem value="SELECT_ALL">

                                    <Checkbox

                                        checked={
                                            selectedProducts.length ===
                                            (currentConfig.products || []).length
                                        }
                                        indeterminate={
                                            selectedProducts.length >
                                            0 &&
                                            selectedProducts.length <
                                            (currentConfig.products || []).length
                                        }

                                    />

                                    <ListItemText
                                        primary="Select All"
                                    />

                                </MenuItem>

                                {(currentConfig.products || []).map((item) => {
                                    const optionValue = getOptionValue(item);
                                    const optionLabel = getOptionLabel(item);
                                    return (
                                        <MenuItem
                                            key={optionValue}
                                            value={optionValue}
                                        >
                                            <Checkbox
                                                checked={selectedProducts.includes(
                                                    optionValue
                                                )}
                                            />

                                            <ListItemText
                                                primary={optionLabel}
                                            />
                                        </MenuItem>
                                    );
                                })}

                            </Select>

                        </FormControl>

                    </Box>

                    <Button
                        variant="contained"
                        onClick={handleApplyFilter}
                        sx={{
                            height: "35px",
                            borderRadius: "8px",
                            textTransform: "none",
                            backgroundColor: "#4F46E5",
                        }}
                    >
                        Apply Filter
                    </Button>

                </Box>
                <Box sx={{ mt: 3 }}>

                    <Tabs
                        value={activeTab}
                        onChange={(_, value) =>
                            setActiveTab(value)
                        }
                    >

                        {EVENT_TABS.map((tab) => (

                            <Tab
                                key={tab.value}
                                value={tab.value}
                                label={tab.label}
                            />

                        ))}

                    </Tabs>

                </Box>
                <Accordion
                    defaultExpanded
                    sx={{
                        mt: 2,
                        borderRadius: "12px !important",
                        border: "1px solid #D8DEE8",
                        boxShadow: "none",
                    }}
                >

                    <AccordionSummary
                        expandIcon={<ExpandMoreIcon />}
                    >

                        <Box
                            sx={{
                                width: "100%",
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                            }}
                        >

                            <Typography
                                sx={{
                                    fontWeight: 700,
                                }}
                            >
                                Impact Curve Configuration
                            </Typography>

                            <Box>

                                <Button
                                    variant="contained"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        // handleRunCalculation();
                                    }}
                                    sx={{
                                        height: "33px",
                                        textTransform: "none",
                                        borderRadius: "8px",
                                        backgroundColor: "#4F46E5",
                                        px: 1.5,
                                        fontWeight: 600,
                                        marginRight: "12px",
                                    }}
                                >
                                    Run Calculation
                                </Button>

                                <Button
                                    variant="contained"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleAddNewEvent();
                                    }}
                                    sx={{
                                        height: "33px",
                                        textTransform: "none",
                                        borderRadius: "8px",
                                        backgroundColor: "#4F46E5",
                                        px: 1.5,
                                        fontWeight: 600,
                                        whiteSpace: "nowrap",
                                    }}
                                >
                                    + Add New Event
                                </Button>
                            </Box>
                        </Box>
                    </AccordionSummary>

                    <AccordionDetails>

                        <Paper
                            sx={{
                                mt: 1,
                                border: "1px solid #D8DEE8",
                                borderRadius: "12px",
                                overflowX: "auto",
                                overflowY: "auto",
                                maxHeight: 380,
                                boxShadow: "none",
                            }}
                        >

                            {/* HEADER */}

                            <Box
                                sx={{
                                    display: "grid",
                                    gridTemplateColumns: headerColumns,
                                    gap: 2,
                                    px: 2,
                                    py: 1.5,
                                    backgroundColor: "#f8fafc",
                                    borderBottom: "1px solid #D8DEE8",
                                    minWidth: isOverallEvent ? 900 : 1450,
                                }}
                            >

                                {headers.map((item) => (

                                    <Typography
                                        key={item}
                                        sx={{
                                            fontSize: 13,
                                            fontWeight: 700,
                                            color: "#64748b",
                                        }}
                                    >
                                        {item}
                                    </Typography>

                                ))}

                            </Box>

                            {/* ROWS */}

                            {eventRows.map((row, index) => (

                                <Box
                                    key={index}
                                    sx={{
                                        display: "grid",
                                        gridTemplateColumns: headerColumns,
                                        gap: 2,
                                        px: 2,
                                        py: 1.5,
                                        alignItems: "center",
                                        minWidth: isOverallEvent ? 900 : 1450,
                                    }}
                                >

                                    {/* MARKET EVENT */}

                                    {isMarketEvent && (
                                        <>

                                            {/* EVENT */}

                                            <TextField
                                                value={row.event_name}
                                                placeholder="Payer Event"
                                                size="small"
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "event_name",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* PRODUCTS */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    multiple
                                                    MenuProps={menuProps}
                                                    value={row.products}
                                                    renderValue={(selected) =>
                                                        renderOptionValue(
                                                            selected,
                                                            currentConfig.products || [],
                                                            "Select"
                                                        )
                                                    }
                                                    onChange={(e) => {

                                                        const value = e.target.value;

                                                        if (value.includes("SELECT_ALL")) {

                                                            handleRowChange(
                                                                index,
                                                                "products",
                                                                row.products.length ===
                                                                    (currentConfig.products || []).length
                                                                    ? []
                                                                    : currentConfig.products || []
                                                            );

                                                        } else {

                                                            handleRowChange(
                                                                index,
                                                                "products",
                                                                value
                                                            );

                                                        }

                                                    }}
                                                >
                                                    <MenuItem value="SELECT_ALL">

                                                        <Checkbox
                                                            size="small"
                                                            checked={
                                                                row.products.length ===
                                                                (currentConfig.products || []).length
                                                            }
                                                            indeterminate={
                                                                row.products.length > 0 &&
                                                                row.products.length <
                                                                (currentConfig.products || []).length
                                                            }
                                                        />

                                                        <ListItemText primary="Select All" />

                                                    </MenuItem>

                                                    {(currentConfig.products || []).map((item) => {
                                                        const optionValue = getOptionValue(item);
                                                        const optionLabel = getOptionLabel(item);
                                                        return (
                                                            <MenuItem
                                                                key={optionValue}
                                                                value={optionValue}
                                                                sx={{
                                                                    py: 0.5,
                                                                }}
                                                            >

                                                                <Checkbox
                                                                    checked={row.products.includes(optionValue)}
                                                                    size="small"
                                                                />

                                                                <ListItemText
                                                                    primary={optionLabel}
                                                                />

                                                            </MenuItem>
                                                        );
                                                    })}

                                                </Select>

                                            </FormControl>

                                            {/* MARKETS */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    multiple
                                                    MenuProps={menuProps}
                                                    value={row.markets}
                                                    renderValue={(selected) =>
                                                        renderOptionValue(
                                                            selected,
                                                            currentConfig.markets || [],
                                                            "Select"
                                                        )
                                                    }
                                                    onChange={(e) => {

                                                        const value = e.target.value;

                                                        if (value.includes("SELECT_ALL")) {

                                                            handleRowChange(
                                                                index,
                                                                "markets",
                                                                row.markets.length ===
                                                                    (currentConfig.markets || []).length
                                                                    ? []
                                                                    : currentConfig.markets || []
                                                            );

                                                        } else {

                                                            handleRowChange(
                                                                index,
                                                                "markets",
                                                                value
                                                            );

                                                        }

                                                    }}
                                                >

                                                    <MenuItem value="SELECT_ALL">

                                                        <Checkbox
                                                            size="small"
                                                            checked={
                                                                row.markets.length ===
                                                                (currentConfig.markets || []).length
                                                            }
                                                            indeterminate={
                                                                row.markets.length > 0 &&
                                                                row.markets.length <
                                                                (currentConfig.markets || []).length
                                                            }
                                                        />

                                                        <ListItemText primary="Select All" />

                                                    </MenuItem>

                                                    {(currentConfig.markets || []).map((item) => {
                                                        const optionValue = getOptionValue(item);
                                                        const optionLabel = getOptionLabel(item);
                                                        return (
                                                            <MenuItem
                                                                key={optionValue}
                                                                value={optionValue}
                                                                sx={{
                                                                    py: 0.5,
                                                                }}
                                                            >

                                                                <Checkbox
                                                                    checked={row.markets.includes(optionValue)}
                                                                    size="small"
                                                                />

                                                                <ListItemText
                                                                    primary={optionLabel}
                                                                />

                                                            </MenuItem>
                                                        );
                                                    })}

                                                </Select>

                                            </FormControl>

                                            {/* IMPACTED */}

                                            <Button
                                                variant="outlined"
                                                onClick={() =>
                                                    handleOpenImpactDialog(index)
                                                }
                                                sx={{
                                                    textTransform: "none",
                                                    borderRadius: "6px",
                                                    height: "32px",
                                                    fontSize: "12px",
                                                    minWidth: "90px",
                                                }}
                                            >
                                                Edit Source
                                            </Button>

                                            {/* START DATE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.start_date}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "start_date",
                                                            e.target.value
                                                        )
                                                    }
                                                >

                                                    {availableMonths.map((month) => (

                                                        <MenuItem
                                                            key={month}
                                                            value={month}
                                                        >
                                                            {dayjs(month).format("MMM YY")}
                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

                                            {/* PEAK */}

                                            <TextField
                                                size="small"
                                                value={row.peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* MONTHS */}

                                            <TextField
                                                size="small"
                                                value={row.months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* CURVE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.curve_type}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "curve_type",
                                                            e.target.value
                                                        )
                                                    }
                                                >

                                                    {(currentConfig.curve_types || []).map((item) => (

                                                        <MenuItem
                                                            key={item}
                                                            value={item}
                                                        >
                                                            {item}
                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

                                            {/* FACTOR */}

                                            <TextField
                                                size="small"
                                                value={row.factor}
                                                disabled={
                                                    row.curve_type === "Linear"
                                                }
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "factor",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            row.curve_type === "Linear"
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            <Switch
                                                size="small"
                                                checked={row.enable_coverage}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "enable_coverage",
                                                        e.target.checked
                                                    )
                                                }
                                            />

                                            {/* COVERAGE % */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE CURVE */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_curve}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_curve",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE FACTOR */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_factor}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_factor",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE MONTH */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* MENU */}

                                            <Box
                                                sx={{
                                                    display: "flex",
                                                    justifyContent: "center",
                                                    cursor: "pointer",
                                                }}
                                                onClick={(event) =>
                                                    handleOpenMenu(event, index)
                                                }
                                            >
                                                <MoreVertIcon fontSize="small" />
                                            </Box>

                                        </>
                                    )}

                                    {isProductEvent && (
                                        <>

                                            {/* PRODUCT EVENT */}

                                            <TextField
                                                value={row.event_name}
                                                placeholder="Product Event"
                                                size="small"
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "event_name",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* PRODUCTS */}
                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    multiple
                                                    MenuProps={menuProps}
                                                    value={row.products}
                                                    renderValue={(selected) =>
                                                        renderOptionValue(
                                                            selected,
                                                            currentConfig.products || [],
                                                            "Select"
                                                        )
                                                    }
                                                    onChange={(e) => {

                                                        const value = e.target.value;

                                                        if (value.includes("SELECT_ALL")) {

                                                            handleRowChange(
                                                                index,
                                                                "products",
                                                                row.products.length ===
                                                                    (currentConfig.products || []).length
                                                                    ? []
                                                                    : currentConfig.products || []
                                                            );

                                                        } else {

                                                            handleRowChange(
                                                                index,
                                                                "products",
                                                                value
                                                            );

                                                        }

                                                    }}
                                                >

                                                    <MenuItem value="SELECT_ALL">

                                                        <Checkbox
                                                            size="small"
                                                            checked={
                                                                row.products.length ===
                                                                (currentConfig.products || []).length
                                                            }
                                                            indeterminate={
                                                                row.products.length > 0 &&
                                                                row.products.length <
                                                                (currentConfig.products || []).length
                                                            }
                                                        />

                                                        <ListItemText primary="Select All" />

                                                    </MenuItem>

                                                    {(currentConfig.products || []).map((item) => {
                                                        const optionValue = getOptionValue(item);
                                                        const optionLabel = getOptionLabel(item);
                                                        return (
                                                            <MenuItem
                                                                key={optionValue}
                                                                value={optionValue}
                                                                sx={{
                                                                    py: 0.5,
                                                                }}
                                                            >

                                                                <Checkbox
                                                                    checked={row.products.includes(optionValue)}
                                                                    size="small"
                                                                />

                                                                <ListItemText
                                                                    primary={optionLabel}
                                                                />

                                                            </MenuItem>
                                                        );
                                                    })}

                                                </Select>

                                            </FormControl>

                                            {/* MARKETS */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    multiple
                                                    MenuProps={menuProps}
                                                    value={row.markets}
                                                    renderValue={(selected) =>
                                                        renderOptionValue(
                                                            selected,
                                                            currentConfig.markets || [],
                                                            "Select"
                                                        )
                                                    }
                                                    onChange={(e) => {

                                                        const value = e.target.value;

                                                        if (value.includes("SELECT_ALL")) {

                                                            handleRowChange(
                                                                index,
                                                                "markets",
                                                                row.markets.length ===
                                                                    (currentConfig.markets || []).length
                                                                    ? []
                                                                    : currentConfig.markets || []
                                                            );

                                                        } else {

                                                            handleRowChange(
                                                                index,
                                                                "markets",
                                                                value
                                                            );

                                                        }

                                                    }}
                                                >

                                                    <MenuItem value="SELECT_ALL">

                                                        <Checkbox
                                                            size="small"
                                                            checked={
                                                                row.markets.length ===
                                                                (currentConfig.markets || []).length
                                                            }
                                                            indeterminate={
                                                                row.markets.length > 0 &&
                                                                row.markets.length <
                                                                (currentConfig.markets || []).length
                                                            }
                                                        />

                                                        <ListItemText primary="Select All" />

                                                    </MenuItem>

                                                    {(currentConfig.markets || []).map((item) => {
                                                        const optionValue = getOptionValue(item);
                                                        const optionLabel = getOptionLabel(item);
                                                        return (
                                                            <MenuItem
                                                                key={optionValue}
                                                                value={optionValue}
                                                                sx={{
                                                                    py: 0.5,
                                                                }}
                                                            >

                                                                <Checkbox
                                                                    checked={row.markets.includes(optionValue)}
                                                                    size="small"
                                                                />

                                                                <ListItemText
                                                                    primary={optionLabel}
                                                                />

                                                            </MenuItem>
                                                        );
                                                    })}

                                                </Select>

                                            </FormControl>

                                            {/* IMPACTED PRODUCTS */}

                                            <Button
                                                variant="outlined"
                                                onClick={() =>
                                                    handleOpenImpactDialog(index)
                                                }
                                                sx={{
                                                    textTransform: "none",
                                                    borderRadius: "6px",
                                                    height: "32px",
                                                    fontSize: "12px",
                                                    minWidth: "90px",
                                                }}
                                            >
                                                Edit Source
                                            </Button>

                                            {/* START DATE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.start_date}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "start_date",
                                                            e.target.value
                                                        )
                                                    }
                                                >

                                                    {availableMonths.map((month) => (

                                                        <MenuItem
                                                            key={month}
                                                            value={month}
                                                        >
                                                            {dayjs(month).format("MMM YY")}
                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

                                            {/* PEAK % */}

                                            <TextField
                                                size="small"
                                                value={row.peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* MONTHS */}

                                            <TextField
                                                size="small"
                                                value={row.months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* CURVE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.curve_type}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "curve_type",
                                                            e.target.value
                                                        )
                                                    }
                                                >

                                                    {(currentConfig.curve_types || []).map((item) => (

                                                        <MenuItem
                                                            key={item}
                                                            value={item}
                                                        >
                                                            {item}
                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

                                            {/* FACTOR */}

                                            <TextField
                                                size="small"
                                                value={row.factor}
                                                disabled={
                                                    row.curve_type === "Linear"
                                                }
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "factor",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            row.curve_type === "Linear"
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            <Switch
                                                size="small"
                                                checked={row.enable_coverage}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "enable_coverage",
                                                        e.target.checked
                                                    )
                                                }
                                            />

                                            {/* COVERAGE PEAK % */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE CURVE */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_curve}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_curve",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE FACTOR */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_factor}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_factor",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE PEAK MONTHS */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* MENU */}

                                            <Box
                                                sx={{
                                                    display: "flex",
                                                    justifyContent: "center",
                                                    cursor: "pointer",
                                                }}
                                                onClick={(event) =>
                                                    handleOpenMenu(event, index)
                                                }
                                            >
                                                <MoreVertIcon fontSize="small" />
                                            </Box>

                                        </>
                                    )}

                                    {isOverallEvent && (
                                        <>
                                            {/* OVERALL EVENT */}

                                            <TextField
                                                value={row.event_name}
                                                placeholder="Overall Event"
                                                size="small"
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "event_name",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* START DATE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.start_date}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "start_date",
                                                            e.target.value
                                                        )
                                                    }
                                                >

                                                    {availableMonths.map((month) => (

                                                        <MenuItem
                                                            key={month}
                                                            value={month}
                                                        >
                                                            {dayjs(month).format("MMM YY")}
                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

                                            {/* PEAK % */}

                                            <TextField
                                                size="small"
                                                value={row.peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* MONTHS */}

                                            <TextField
                                                size="small"
                                                value={row.months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={tableInputStyle}
                                            />

                                            {/* CURVE */}

                                            <FormControl
                                                size="small"
                                                sx={tableSelectStyle}
                                            >
                                                <Select
                                                    value={row.curve_type}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "curve_type",
                                                            e.target.value
                                                        )
                                                    }
                                                >

                                                    {(currentConfig.curve_types || []).map((item) => (

                                                        <MenuItem
                                                            key={item}
                                                            value={item}
                                                        >
                                                            {item}
                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

                                            {/* FACTOR */}

                                            <TextField
                                                size="small"
                                                value={row.factor}
                                                disabled={
                                                    row.curve_type === "Linear"
                                                }
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "factor",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            row.curve_type === "Linear"
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            <Switch
                                                size="small"
                                                checked={row.enable_coverage}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "enable_coverage",
                                                        e.target.checked
                                                    )
                                                }
                                            />

                                            {/* COVERAGE PEAK % */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_percent}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_percent",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* COVERAGE PEAK MONTHS */}

                                            <TextField
                                                size="small"
                                                disabled={!row.enable_coverage}
                                                value={row.coverage_peak_months}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "coverage_peak_months",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    ...tableInputStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableInputStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor:
                                                            !row.enable_coverage
                                                                ? "#F3F4F6"
                                                                : "#fff",
                                                    },
                                                }}
                                            />

                                            {/* MENU */}

                                            <Box
                                                sx={{
                                                    display: "flex",
                                                    justifyContent: "center",
                                                    cursor: "pointer",
                                                }}
                                                onClick={(event) =>
                                                    handleOpenMenu(event, index)
                                                }
                                            >
                                                <MoreVertIcon fontSize="small" />
                                            </Box>

                                        </>
                                    )}

                                </Box>

                            ))}

                        </Paper>

                    </AccordionDetails>
                    <HIVImpactCurveChart
                    chartData={currentMetricData.chart}
                    activeTab={activeTab}
                />

            </Accordion>
            <HIVImpactCurveTable
                tableData={currentMetricData.table}
                metricFilters={marketEventMock.metric_filters}
                selectedMetric={selectedMetric}
                setSelectedMetric={setSelectedMetric}
                selectedView={selectedView}
                setSelectedView={setSelectedView}
                activeTab={activeTab}
            />

                <Menu
                    anchorEl={menuAnchorEl}
                    open={Boolean(menuAnchorEl)}
                    onClose={handleCloseMenu}
                >

                    <MenuItem
                        onClick={() => {
                            handleDuplicateRow();
                            handleCloseMenu();
                        }}
                    >
                        Duplicate
                    </MenuItem>

                    <MenuItem
                        sx={{
                            color: "error.main",
                        }}
                        onClick={() => {
                            setOpenDeleteDialog(true);
                            handleCloseMenu();
                        }}
                    >
                        Delete
                    </MenuItem>

                </Menu>
                <Dialog
                    open={openDeleteDialog}
                    onClose={() => setOpenDeleteDialog(false)}
                    maxWidth="xs"
                    fullWidth
                >

                    <DialogTitle>
                        Delete Event
                    </DialogTitle>

                    <DialogContent>

                        <Typography>
                            Are you sure you want to delete this event?
                        </Typography>

                    </DialogContent>

                    <DialogActions>

                        <Button
                            onClick={() =>
                                setOpenDeleteDialog(false)
                            }
                        >
                            Cancel
                        </Button>

                        <Button
                            color="error"
                            variant="contained"
                            onClick={handleDeleteRow}
                        >
                            Delete
                        </Button>

                    </DialogActions>

                </Dialog>
                <Dialog
                    open={openImpactDialog}
                    onClose={handleCloseImpactDialog}
                    maxWidth="sm"
                    fullWidth
                >
                    <DialogTitle
                        sx={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                        }}
                    >

                        {isMarketEvent
                            ? "Edit Impacted Payers"
                            : "Edit Impacted Products"}

                        <IconButton
                            onClick={handleCloseImpactDialog}
                        >
                            <CloseIcon />
                        </IconButton>

                    </DialogTitle>
                    <DialogContent>

                        <Typography
                            sx={{
                                mb: 2,
                                fontWeight: 600,
                            }}
                        >
                            Select impacted items
                        </Typography>

                        <FormControl fullWidth>

                            <Select
                                multiple
                                value={
                                    selectedImpactRowIndex !== null
                                        ? eventRows[selectedImpactRowIndex]
                                            ?.impacted_items || []
                                        : []
                                }
                                renderValue={(selected) =>
                                    renderOptionValue(
                                        selected,
                                        isMarketEvent
                                            ? currentConfig.impacted_markets || []
                                            : currentConfig.impacted_products || [],
                                        "Select"
                                    )
                                }
                                onChange={(e) =>
                                    handleImpactSelection(
                                        e.target.value
                                    )
                                }
                            >
                                {(isMarketEvent
                                    ? currentConfig.impacted_markets
                                    : currentConfig.impacted_products
                                )?.map((item) => {
                                    const optionValue = getOptionValue(item);
                                    const optionLabel = getOptionLabel(item);
                                    return (
                                        <MenuItem
                                            key={optionValue}
                                            value={optionValue}
                                        >

                                            <Checkbox
                                                checked={
                                                    selectedImpactRowIndex !==
                                                    null &&
                                                    eventRows[
                                                        selectedImpactRowIndex
                                                    ]?.impacted_items.includes(
                                                        optionValue
                                                    )
                                                }
                                            />

                                            <ListItemText
                                                primary={optionLabel}
                                            />

                                        </MenuItem>
                                    );
                                })}

                            </Select>

                        </FormControl>

                    </DialogContent>
                    <DialogActions>

                        <Button
                            onClick={handleCloseImpactDialog}
                        >
                            Cancel
                        </Button>

                        <Button
                            variant="contained"
                            onClick={handleCloseImpactDialog}
                        >
                            Apply
                        </Button>

                    </DialogActions>

                </Dialog>
            </Paper>


        </Box>

    );
}