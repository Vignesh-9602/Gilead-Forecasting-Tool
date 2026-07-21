import React, { useContext, useEffect, useState } from "react";

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
// import { marketEventMock } from "./MEMockData";
import { marketEventMock } from "./updatedMock";
import HIVImpactCurveChart from "./HIVMEChart";
import HIVImpactCurveTable from "./HIVMETable";
import { getHIVMarketEventFilters, applyHIVMarketEventFilter, runHIVMarketEventCalculation, editHIVImpactCurveTable } from "../../../services/apiService";
import { useSnackbarStore, useLoadingStore } from "../../../stores";

const globalConfigDateLocaleText = {
    fieldMonthPlaceholder: () => "MM",
    fieldYearPlaceholder: () => "YYYY",
};

export default function HIVMarketEvent() {

    const { favState } = useContext(GlobalContext);

    const { showSnackbar } = useSnackbarStore();
    const { setLoading } = useLoadingStore();

    const therapyArea =
        favState?.selectedTherapyArea || "HIV Treatment";

    const [availableMonths, setAvailableMonths] = useState([]);
    const [availableScenarios, setAvailableScenarios] = useState([]);

    const [eventTabsData, setEventTabsData] = useState({});

    const [scenarioName, setScenarioName] = useState("");

    const [selectedMarkets, setSelectedMarkets] = useState([]);
    const [selectedProducts, setSelectedProducts] = useState([]);

    const [fromDate, setFromDate] = useState("");
    const [toDate, setToDate] = useState("");
    const [availableMarkets, setAvailableMarkets] = useState([]);
    const [availableProducts, setAvailableProducts] = useState([]);

    const [activeTab, setActiveTab] =
        useState("overall_event");

    const isMarketEvent =
        activeTab === "market_event";

    const isProductEvent =
        activeTab === "product_event";

    const isOverallEvent =
        activeTab === "overall_event";

    const [eventRows, setEventRows] =
        useState([]);

    const [selectedMetric, setSelectedMetric] =
        useState("market_share");

    const [selectedView, setSelectedView] =
        useState("monthly");

    const [metricFilters, setMetricFilters] =
        useState([]);

    const [selectedTableView, setSelectedTableView] =
        useState("");

    const [editedTableRows, setEditedTableRows] =
        useState([]);


    // useEffect(() => {

    //     if (!currentConfig) return;

    //     const rows = currentConfig.rows || [];

    //     setEventRows(
    //         rows.length
    //             ? rows
    //             : [createEmptyRow(currentConfig)]
    //     );

    // }, [activeTab, eventTabsData]);

    useEffect(() => {

        if (!currentConfig) return;

        const rows = currentConfig.rows || [];

        const normalizedRows = rows.length
            ? rows.map((row) => ({
                ...createEmptyRow(currentConfig),
                ...row,
            }))
            : [createEmptyRow(currentConfig)];

        setEventRows(normalizedRows);

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
        ] || {};

    const effectiveTableView =
        selectedTableView ||
        currentMetricData?.selected_view ||
        currentMetricData?.view_options?.[0]?.value;

    const currentDisplay =
        currentMetricData?.[effectiveTableView];

    useEffect(() => {

        const options =
            currentMetricData?.view_options || [];

        if (options.length) {

            setSelectedTableView(
                currentMetricData.selected_view ||
                options[0].value
            );

        }

    }, [activeTab, selectedView]);

    const impactOptions =
        isMarketEvent
            ? currentConfig.impact_markets || []
            : currentConfig.impact_products || [];

    const createEmptyRow = (config) => ({

        id: Date.now(),

        event_name: "",

        products: [],

        markets: [],

        impacted_items: [],
        source_percentages: {},

        start_date:
            config.forecast_start_date || "",

        peak_percent: "",

        months: "",

        curve_type:
            config.curve_types?.[0] || "",

        factor: "",

        enable_coverage: false,

        coverage_peak_percent: "",

        coverage_peak_months: "",

        coverage_curve_type: config.curve_types?.[0] || "",

        coverage_factor: "",

    });

    const [menuAnchorEl, setMenuAnchorEl] =
        useState(null);

    const [selectedRowIndex, setSelectedRowIndex] =
        useState(null);

    const [openDeleteDialog, setOpenDeleteDialog] =
        useState(false);

    const [openImpactDialog, setOpenImpactDialog] =
        useState(false);

    // const [selectedImpactRowIndex, setSelectedImpactRowIndex] =
    //     useState(null);

    const [impactValues, setImpactValues] = useState({});

    const [editedFields, setEditedFields] = useState([]);

    useEffect(() => {
        if (therapyArea) {
            fetchFilters();
        }
    }, [therapyArea]);

    // useEffect(() => {

    //     if (!openImpactDialog) return;

    //     const source = isMarketEvent
    //         ? currentConfig.impact_markets || []
    //         : currentConfig.impact_products || [];

    //     const initial = {};

    //     source.forEach((item) => {
    //         initial[item] = 0;
    //     });

    //     setImpactValues(initial);

    // }, [openImpactDialog, activeTab, currentConfig]);

    const fetchFilters = async () => {
        try {
            setLoading(true);

            const { data: response } =
                await getHIVMarketEventFilters(therapyArea);

            setAvailableScenarios(
                response.available_scenarios || []
            );

            setAvailableMonths(
                response.available_months || []
            );

            setAvailableMarkets(response.markets || []);
            setAvailableProducts(response.products || []);

            const filter = response.selected_filter || {};

            setScenarioName(
                filter.scenario_name || ""
            );

            setSelectedMarkets(
                filter.markets || []
            );

            setSelectedProducts(
                filter.products || []
            );

            setFromDate(
                filter.start_date || ""
            );

            setToDate(
                filter.end_date || ""
            );

            // Auto populate the screen
            await handleApplyFilter(filter);

        } catch (error) {
            console.error(
                "Failed to fetch market event filters",
                error
            );
            showSnackbar(
                "Failed to fetch market event filters",
                "error"
            );
        } finally {
            setLoading(false);
        }
    };

    // const handleApplyFilter = () => {

    //     const payload = {
    //         ta_name: therapyArea,

    //         scenario_name: scenarioName,

    //         markets: selectedMarkets,

    //         products: selectedProducts,

    //         start_date: fromDate,

    //         end_date: toDate,
    //     };

    //     console.log(payload);
    //     const rows = currentConfig.rows || [];

    //     const response = marketEventMock;

    //     setEventTabsData(response.event_tabs);

    //     setEventRows(
    //         rows.length
    //             ? rows
    //             : [createEmptyRow(currentConfig)]
    //     );
    // };

    const handleRunCalculation = async () => {

        const payload = {

            ta_name: therapyArea,

            selected_filter: {

                scenario_name: scenarioName,

                markets: selectedMarkets,

                products: selectedProducts,

                start_date: fromDate,

                end_date: toDate,

            },

            selected_tab: activeTab,

            impact_curve_configuration: {

                rows: eventRows.map((row) => {

                    const payloadRow = {

                        event_name: row.event_name,

                        start_date: row.start_date,

                        peak_percent: Number(row.peak_percent),

                        months: Number(row.months),

                        curve_type: row.curve_type,

                        factor:
                            row.curve_type === "Linear"
                                ? 0
                                : Number(row.factor),

                    };

                    if (activeTab !== "overall_event") {

                        payloadRow.products =
                            row.products;

                        payloadRow.markets =
                            row.markets;

                        if (activeTab === "market_event") {

                            payloadRow.impacted_markets =
                                row.impacted_items || [];

                        } else {

                            payloadRow.impacted_products =
                                row.impacted_items || [];

                        }

                        payloadRow.source_percentages =
                            row.source_percentages || {};

                    }

                    if (row.enable_coverage) {

                        payloadRow.coverage_peak_percent =
                            Number(
                                row.coverage_peak_percent
                            );

                        payloadRow.coverage_peak_months =
                            Number(
                                row.coverage_peak_months
                            );

                        payloadRow.coverage_curve_type =
                            row.coverage_curve_type;

                        payloadRow.coverage_factor =
                            row.coverage_curve_type ===
                                "Linear"
                                ? 0
                                : Number(
                                    row.coverage_factor
                                );

                    }

                    return payloadRow;

                }),

            },


        };

        // console.log("payload--------->", payload)
        try {

            setLoading(true);

            const { data: response } =
                await runHIVMarketEventCalculation(
                    payload
                );

            setEventTabsData(
                response.event_tabs || {}
            );

            setSelectedMetric(
                response.metric_filters?.[0]
                    ?.value || "market_share"
            );

            setMetricFilters(
                response.metric_filters || []
            );

            setSelectedView("monthly");
            showSnackbar(
                "Calculation completed successfully",
                "success"
            );

        } catch (error) {

            console.error(error);

            showSnackbar(
                "Failed to run calculation",
                "error"
            );

        } finally {

            setLoading(false);

        }

    };


    const handleApplyFilter = async (selectedFilter = null) => {

        const payload = {
            ta_name: therapyArea,

            selected_filter: selectedFilter || {
                scenario_name: scenarioName,
                start_date: fromDate,
                end_date: toDate,
                markets: selectedMarkets,
                products: selectedProducts,
            },
        };

        try {

            setLoading(true);

            const { data: response } =
                await applyHIVMarketEventFilter(payload);

            setEventTabsData(
                response.event_tabs || {}
            );

            setSelectedMetric(
                response.metric_filters?.[0]?.value ||
                "market_share"
            );

            setMetricFilters(
                response.metric_filters || []
            );

            setSelectedView("monthly");

            showSnackbar(
                "Filters applied successfully",
                "success"
            );

        } catch (error) {

            console.error(error);

            showSnackbar(
                "Failed to apply filters",
                "error"
            );

        } finally {

            setLoading(false);

        }

    };

    const handleEditRefresh = async (editedFields) => {

        const payload = {

            ta_name: therapyArea,

            selected_filter: {

                scenario_name: scenarioName,

                start_date: fromDate,

                end_date: toDate,

                markets: selectedMarkets,

                products: selectedProducts,

            },

            selected_tab: activeTab,

            selected_metric: selectedMetric,

            selected_table_view: effectiveTableView,

            edited_table_rows: editedTableRows,

            edited_rows: editedFields,

        };

        // console.log("payload-------->", payload)

        try {

            setLoading(true);

            const { data: response } =
                await editHIVImpactCurveTable(
                    payload
                );

            setEventTabsData(
                response.event_tabs || {}
            );

            showSnackbar(
                "Table updated successfully",
                "success"
            );

            return true; //tell child API succeeded

        } catch (error) {

            showSnackbar(
                "Failed to update table",
                "error"
            );
            return false; // stay in edit mode

        } finally {

            setLoading(false);

        }

    };

    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "170px",

        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
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
            label: "Overall Event",
            value: "overall_event",
        },
        {
            label: "Channel Event",
            value: "market_event",
        },
        {
            label: "Product Event",
            value: "product_event",
        }
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

    // const handleOpenImpactDialog = (
    //     index
    // ) => {

    //     setSelectedImpactRowIndex(index);

    //     setOpenImpactDialog(true);

    // };

    const handleOpenImpactDialog = (index) => {

        setSelectedRowIndex(index);

        const row = eventRows[index];

        const source = isMarketEvent
            ? currentConfig.impact_markets || []
            : currentConfig.impact_products || [];

        const values = {};

        source.forEach((item) => {
            values[item] =
                row.source_percentages?.[item] ?? 0;
        });

        setImpactValues(values);

        setOpenImpactDialog(true);

    };

    const handleSaveImpactDialog = () => {

        const selectedItems =
            isMarketEvent
                ? eventRows[selectedRowIndex].markets
                : eventRows[selectedRowIndex].products;

        const impactedItems = impactOptions.filter(
            (item) => !selectedItems.includes(item)
        );

        const updatedRows = [...eventRows];

        updatedRows[selectedRowIndex] = {
            ...updatedRows[selectedRowIndex],
            impacted_items: impactedItems,
            source_percentages: impactValues,
        };

        setEventRows(updatedRows);

        setOpenImpactDialog(false);

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
            updated[index].coverage_peak_months = "";
            updated[index].coverage_curve_type = "";
            updated[index].coverage_factor = "";
        }

        setEventRows(updated);

    };

    // const handleImpactSelection = (
    //     value
    // ) => {

    //     const updated = [...eventRows];

    //     updated[
    //         selectedImpactRowIndex
    //     ].impacted_items = value;

    //     setEventRows(updated);

    // };

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

    const headerColumns = isOverallEvent
        ? "0.9fr 0.45fr 0.35fr 0.35fr 0.45fr 0.3fr 0.3fr 0.45fr 0.45fr 0.45fr 0.3fr 40px"
        : "0.8fr 0.6fr 0.55fr 0.65fr 0.45fr 0.35fr 0.35fr 0.45fr 0.3fr 0.3fr 0.45fr 0.45fr 0.45fr 0.3fr 40px"

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
            "Coverage Curve",
            "Coverage Factor",
            "",
        ]
        : isMarketEvent
            ? [
                "Channel Event",
                "Products",
                "Channel",
                "Impacted Channel",
                "Start Date",
                "Peak %",
                "Months",
                "Curve",
                "Factor",
                "Coverage",
                "Coverage Peak %",
                "Coverage Peak Months",
                "Coverage Curve",
                "Coverage Factor",
                "",
            ]
            : [
                "Product Event",
                "Channel",
                "Products",
                "Impacted Products",
                "Start Date",
                "Peak %",
                "Months",
                "Curve",
                "Factor",
                "Coverage",
                "Coverage Peak %",
                "Coverage Peak Months",
                "Coverage Curve",
                "Coverage Factor",
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

                    {/* Market */}

                    <Box>

                        <Typography sx={labelStyle}>
                            CHANNEL FILTER
                        </Typography>

                        <FormControl sx={inputStyle}>

                            <Select
                                multiple
                                value={selectedMarkets}
                                onChange={(e) => {

                                    const value =
                                        e.target.value;

                                    if (
                                        value.includes(
                                            "SELECT_ALL"
                                        )
                                    ) {

                                        if (
                                            selectedMarkets.length ===
                                            (availableMarkets || []).length
                                        ) {

                                            setSelectedMarkets([]);

                                        } else {

                                            setSelectedMarkets(
                                                availableMarkets || []
                                            );

                                        }

                                    } else {

                                        setSelectedMarkets(
                                            value
                                        );

                                    }

                                }}
                                renderValue={(selected) =>
                                    selected.join(", ")
                                }
                            >

                                <MenuItem value="SELECT_ALL">

                                    <Checkbox
                                        checked={
                                            selectedMarkets.length ===
                                            (availableMarkets || []).length
                                        }
                                        indeterminate={
                                            selectedMarkets.length > 0 &&
                                            selectedMarkets.length <
                                            (availableMarkets || []).length
                                        }
                                    />

                                    <ListItemText
                                        primary="Select All"
                                    />

                                </MenuItem>

                                {(availableMarkets || []).map((item) => (

                                    <MenuItem
                                        key={item}
                                        value={item}
                                    >

                                        <Checkbox
                                            checked={selectedMarkets.includes(
                                                item
                                            )}
                                        />

                                        <ListItemText
                                            primary={item}
                                        />

                                    </MenuItem>

                                ))}

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
                                            (availableProducts || []).length
                                        ) {

                                            setSelectedProducts(
                                                []
                                            );

                                        } else {

                                            setSelectedProducts(
                                                availableProducts || []
                                            );

                                        }

                                    } else {

                                        setSelectedProducts(
                                            value
                                        );

                                    }

                                }}
                                renderValue={(selected) =>
                                    selected.join(", ")
                                }
                            >

                                <MenuItem value="SELECT_ALL">

                                    <Checkbox

                                        checked={
                                            selectedProducts.length ===
                                            (availableProducts || []).length
                                        }
                                        indeterminate={
                                            selectedProducts.length >
                                            0 &&
                                            selectedProducts.length <
                                            (availableProducts || []).length
                                        }

                                    />

                                    <ListItemText
                                        primary="Select All"
                                    />

                                </MenuItem>

                                {(availableProducts || []).map((item) => (

                                    <MenuItem
                                        key={item}
                                        value={item}
                                    >

                                        <Checkbox
                                            checked={selectedProducts.includes(
                                                item
                                            )}
                                        />

                                        <ListItemText
                                            primary={item}
                                        />

                                    </MenuItem>

                                ))}

                            </Select>

                        </FormControl>

                    </Box>

                    <Button
                        variant="contained"
                        onClick={() => handleApplyFilter()}
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
                                        handleRunCalculation();
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
                                                placeholder="Market Event"
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
                                                        selected.length
                                                            ? selected.join(", ")
                                                            : "Select"
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

                                                    {(currentConfig.products || []).map((item) => (

                                                        <MenuItem
                                                            key={item}
                                                            value={item}
                                                            sx={{
                                                                py: 0.5,
                                                            }}
                                                        >

                                                            <Checkbox
                                                                checked={row.products.includes(item)}
                                                                size="small"
                                                            // sx={{
                                                            //     p: 0.5,
                                                            //     mr: 1,
                                                            // }}
                                                            />

                                                            <ListItemText
                                                                primary={item}
                                                            />

                                                        </MenuItem>

                                                    ))}

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
                                                        selected.length
                                                            ? selected.join(", ")
                                                            : "Select"
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

                                                    {(currentConfig.markets || []).map((item) => (

                                                        <MenuItem
                                                            key={item}
                                                            value={item}
                                                            sx={{
                                                                py: 0.5,
                                                            }}
                                                        >

                                                            <Checkbox
                                                                checked={row.markets.includes(item)}
                                                                size="small"
                                                            // sx={{
                                                            //     p: 0.5,
                                                            //     mr: 1,
                                                            // }}
                                                            />

                                                            <ListItemText
                                                                primary={item}
                                                            />

                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

                                            {/* IMPACTED */}

                                            <Button
                                                variant="outlined"
                                                onClick={() => handleOpenImpactDialog(index)}
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

                                            <FormControl
                                                size="small"
                                                sx={{
                                                    ...tableSelectStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableSelectStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor: !row.enable_coverage
                                                            ? "#F3F4F6"
                                                            : "#fff",
                                                    },
                                                }}
                                            >
                                                <Select
                                                    disabled={!row.enable_coverage}
                                                    value={row.coverage_curve_type}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "coverage_curve_type",
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

                                            <TextField
                                                size="small"
                                                disabled={
                                                    !row.enable_coverage ||
                                                    row.coverage_curve_type === "Linear"
                                                }
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
                                                            !row.enable_coverage ||
                                                                row.coverage_curve_type === "Linear"
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
                                                        selected.length
                                                            ? selected.join(", ")
                                                            : "Select"
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

                                                    {(currentConfig.markets || []).map((item) => (

                                                        <MenuItem
                                                            key={item}
                                                            value={item}
                                                            sx={{
                                                                py: 0.5,
                                                            }}
                                                        >

                                                            <Checkbox
                                                                checked={row.markets.includes(item)}
                                                                size="small"
                                                            // sx={{
                                                            //     p: 0.5,
                                                            //     mr: 1,
                                                            // }}
                                                            />

                                                            <ListItemText
                                                                primary={item}
                                                            />

                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

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
                                                        selected.length
                                                            ? selected.join(", ")
                                                            : "Select"
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

                                                    {(currentConfig.products || []).map((item) => (

                                                        <MenuItem
                                                            key={item}
                                                            value={item}
                                                            sx={{
                                                                py: 0.5,
                                                            }}
                                                        >

                                                            <Checkbox
                                                                checked={row.products.includes(item)}
                                                                size="small"
                                                            // sx={{
                                                            //     p: 0.5,
                                                            //     mr: 1,
                                                            // }}
                                                            />

                                                            <ListItemText
                                                                primary={item}
                                                            />

                                                        </MenuItem>

                                                    ))}

                                                </Select>

                                            </FormControl>

                                            {/* IMPACTED PRODUCTS */}

                                            <Button
                                                variant="outlined"
                                                onClick={() => handleOpenImpactDialog(index)}
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

                                            <FormControl
                                                size="small"
                                                sx={{
                                                    ...tableSelectStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableSelectStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor: !row.enable_coverage
                                                            ? "#F3F4F6"
                                                            : "#fff",
                                                    },
                                                }}
                                            >
                                                <Select
                                                    disabled={!row.enable_coverage}
                                                    value={row.coverage_curve_type}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "coverage_curve_type",
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

                                            <TextField
                                                size="small"
                                                disabled={
                                                    !row.enable_coverage ||
                                                    row.coverage_curve_type === "Linear"
                                                }
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
                                                            !row.enable_coverage ||
                                                                row.coverage_curve_type === "Linear"
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

                                            <FormControl
                                                size="small"
                                                sx={{
                                                    ...tableSelectStyle,
                                                    "& .MuiOutlinedInput-root": {
                                                        ...tableSelectStyle["& .MuiOutlinedInput-root"],
                                                        backgroundColor: !row.enable_coverage
                                                            ? "#F3F4F6"
                                                            : "#fff",
                                                    },
                                                }}
                                            >
                                                <Select
                                                    disabled={!row.enable_coverage}
                                                    value={row.coverage_curve_type}
                                                    MenuProps={menuProps}
                                                    onChange={(e) =>
                                                        handleRowChange(
                                                            index,
                                                            "coverage_curve_type",
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

                                            <TextField
                                                size="small"
                                                disabled={
                                                    !row.enable_coverage ||
                                                    row.coverage_curve_type === "Linear"
                                                }
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
                                                            !row.enable_coverage ||
                                                                row.coverage_curve_type === "Linear"
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
                        chartData={currentDisplay?.chart}
                    />

                </Accordion>
                <HIVImpactCurveTable
                    tableData={currentDisplay?.table}
                    selectedTableView={effectiveTableView}
                    setSelectedTableView={setSelectedTableView}
                    currentMetricData={currentMetricData}
                    // metricFilters={marketEventMock.metric_filters}
                    metricFilters={metricFilters}
                    selectedMetric={selectedMetric}
                    setSelectedMetric={setSelectedMetric}
                    selectedView={selectedView}
                    setSelectedView={setSelectedView}
                    activeTab={activeTab}
                    editedTableRows={editedTableRows}
                    setEditedTableRows={setEditedTableRows}
                    onEditRefresh={
                        handleEditRefresh
                    }
                    setEditedFields={setEditedFields}
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
                    PaperProps={{
                        sx: {
                            width: "320px",
                            maxWidth: "90vw",
                            borderRadius: "12px",
                        },
                    }}
                >
                    <DialogTitle
                        sx={{
                            fontWeight: 700,
                            fontSize: "16px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            pr: 1,
                        }}
                    >
                        {isMarketEvent
                            ? "Impacted Channel (%)"
                            : "Impacted Products (%)"}

                        <IconButton
                            size="small"
                            onClick={handleCloseImpactDialog}
                        >
                            <CloseIcon fontSize="small" />
                        </IconButton>
                    </DialogTitle>

                    <DialogContent>

                        {(() => {

                            const selectedItems =
                                isMarketEvent
                                    ? eventRows[selectedRowIndex]?.markets || []
                                    : eventRows[selectedRowIndex]?.products || [];

                            const impactTotal =
                                impactOptions.reduce(
                                    (sum, item) =>
                                        selectedItems.includes(item)
                                            ? sum
                                            : sum + Number(impactValues[item] || 0),
                                    0
                                );

                            const isImpactValid =
                                impactTotal === 100;

                            return (

                                <>

                                    <Box
                                        sx={{
                                            mt: 1,
                                            display: "flex",
                                            flexDirection: "column",
                                            gap: 2,
                                        }}
                                    >

                                        {impactOptions.map((item) => {

                                            const disabled =
                                                selectedItems.includes(item);

                                            return (

                                                <Box
                                                    key={item}
                                                    sx={{
                                                        display: "flex",
                                                        alignItems: "center",
                                                        gap: 7,
                                                    }}
                                                >

                                                    <Typography
                                                        sx={{
                                                            width: "120px",
                                                            flexShrink: 0,
                                                            fontSize: "14px",
                                                            color: disabled
                                                                ? "#94A3B8"
                                                                : "#334155",
                                                        }}
                                                    >
                                                        {item}
                                                    </Typography>

                                                    <TextField
                                                        type="number"
                                                        size="small"
                                                        disabled={disabled}
                                                        value={
                                                            impactValues[item] ?? 0
                                                        }
                                                        onChange={(e) =>
                                                            setImpactValues((prev) => ({
                                                                ...prev,
                                                                [item]: Number(
                                                                    e.target.value || 0
                                                                ),
                                                            }))
                                                        }
                                                        sx={{
                                                            width: "65px",

                                                            "& .MuiOutlinedInput-root": {
                                                                height: "30px",
                                                                fontSize: "13px",
                                                                backgroundColor:
                                                                    disabled
                                                                        ? "#E2E8F0"
                                                                        : "#fff",
                                                            },

                                                            "& input": {
                                                                padding: "6px 8px",
                                                            },
                                                        }}
                                                    />

                                                </Box>

                                            );

                                        })}

                                        {!isImpactValid && (

                                            <Typography
                                                sx={{
                                                    fontSize: "12px",
                                                    color: "#EF4444",
                                                    mt: 1,
                                                }}
                                            >
                                                Total must equal 100%.
                                            </Typography>

                                        )}

                                    </Box>

                                    <DialogActions
                                        sx={{
                                            p: 0,
                                            pt: 3,
                                        }}
                                    >

                                        <Button
                                            fullWidth
                                            variant="contained"
                                            disabled={!isImpactValid}
                                            onClick={handleSaveImpactDialog}
                                            sx={{
                                                textTransform: "none",
                                                borderRadius: "8px",
                                                height: "42px",
                                                backgroundColor: "#4F46E5",
                                            }}
                                        >
                                            Done
                                        </Button>

                                    </DialogActions>

                                </>

                            );

                        })()}

                    </DialogContent>

                </Dialog>
            </Paper>


        </Box>

    );
}