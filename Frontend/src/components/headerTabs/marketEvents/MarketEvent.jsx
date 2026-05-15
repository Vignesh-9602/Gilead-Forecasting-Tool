import React, { useState, useEffect, useContext } from "react";
import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    Button,
    TextField,
    Menu,
    MenuItem as DropdownMenuItem,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogContentText,
    DialogActions,
} from "@mui/material";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs from "dayjs";
import CloseIcon from "@mui/icons-material/Close";
import IconButton from "@mui/material/IconButton";
import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

import { GlobalContext } from "../../../context/Provider";
import { getMarketEventFilters, applyMarketEventFilters, runMarketEventCalculation } from "../../../services/apiService";
import MarketEventChart from "./MarketEventChart";
import MarketEventOutputTable from "./MarketEventTable";

export default function MarketEvents() {
    const { favState } = useContext(GlobalContext);
    const therapyArea = favState?.selectedTherapyArea;
    const [indication, setIndication] = useState("");
    const [selectedScenario, setSelectedScenario] = useState("");
    const [mappingData, setMappingData] = useState({});
    const [filterOptions, setFilterOptions] = useState({
        indications: [],
    });
    const [sourceOptions, setSourceOptions] = useState([]);
    const [targetProducts, setTargetProducts] = useState([]);
    const [lots, setLots] = useState([]);
    const [curveTypes, setCurveTypes] = useState([]);
    const [forecastStartDate, setForecastStartDate] = useState("");

    const [eventRows, setEventRows] = useState([]);

    const [menuAnchorEl, setMenuAnchorEl] = useState(null);
    const [selectedRowIndex, setSelectedRowIndex] = useState(null);

    const [openDeleteDialog, setOpenDeleteDialog] = useState(false);

    const [openSourceDialog, setOpenSourceDialog] = useState(false);

    const [selectedSourceRowIndex, setSelectedSourceRowIndex] = useState(null);
    const [marketShareChartData, setMarketShareChartData] = useState(null);
    const [marketEventMetricsData, setMarketEventMetricsData] = useState(null);

    useEffect(() => {
        if (therapyArea) {
            fetchFilters();
        }
    }, [therapyArea]);

    const fetchFilters = async () => {
        try {
            const response = await getMarketEventFilters(therapyArea);

            const resData = response?.data;

            setMappingData(resData?.data || {});

            setFilterOptions({
                indications: Object.keys(resData?.data || {}),
            });

        } catch (error) {
            console.error("Failed to fetch market event filters", error);
        }
    };

    const handleApplyFilter = async () => {
        if (!therapyArea || !indication || !selectedScenario) {
            return;
        }

        const payload = {
            ta_name: therapyArea,
            indication,
            scenario_name: selectedScenario,
        };

        try {
            const response =
                await applyMarketEventFilters(payload);

            const data = response?.data;

            // dropdown data
            setLots(data?.lots || []);

            setTargetProducts(
                data?.target_products || []
            );

            setSourceOptions(
                data?.source_products || []
            );

            setCurveTypes(
                data?.curve_types || []
            );

            setForecastStartDate(
                data?.forecast_start_date || ""
            );

            setMarketShareChartData(
                data?.metrics_data?.market_share?.chart || null
            );

            setMarketEventMetricsData(
                data?.metrics_data || null
            );

            // create first default row dynamically
            setEventRows([
                {
                    event_name: "",

                    lot: data?.lots?.[0] || "",

                    target_product:
                        data?.target_products?.[0] || "",

                    start_date:
                        data?.forecast_start_date || "",

                    curve_type:
                        data?.curve_types?.[0] || "",

                    peak_percent: "",
                    months: "",
                    factor: "",

                    source_percentages:
                        (data?.source_products || []).reduce(
                            (acc, item) => {
                                acc[item] = "";
                                return acc;
                            },
                            {}
                        ),
                },
            ]);

        } catch (error) {
            console.error(
                "Failed to apply market event filters",
                error
            );
        }
    };

    const availableScenarios =
        indication
            ? mappingData?.[indication]?.scenarios || []
            : [];

    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "180px",
        "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
            height: "35px",
            backgroundColor: "#fcfcfd",
        },
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

    const handleAddNewEvent = () => {
        const newRow = {
            event_name: "",
            lot: lots?.[0] || "",
            target_product: targetProducts?.[0] || "",
            start_date: forecastStartDate || "",
            curve_type: curveTypes?.[0] || "",
            peak_percent: "",
            months: "",
            factor: "",
            source_percentages:
                createEmptySourcePercentages(),
        };

        setEventRows((prev) => [...prev, newRow]);
    };

    const handleOpenMenu = (event, index) => {
        setMenuAnchorEl(event.currentTarget);
        setSelectedRowIndex(index);
    };

    const handleCloseMenu = () => {
        setMenuAnchorEl(null);
    };

    const handleDuplicateRow = () => {
        if (selectedRowIndex === null) return;

        const selectedRow = eventRows[selectedRowIndex];

        const duplicatedRow = {
            ...selectedRow,

            source_percentages: {
                ...selectedRow.source_percentages,
            },
        };

        const updatedRows = [...eventRows];

        updatedRows.splice(
            selectedRowIndex + 1,
            0,
            duplicatedRow
        );

        setEventRows(updatedRows);

        handleCloseMenu();
    };

    const handleDeleteRow = () => {
        const updatedRows = eventRows.filter(
            (_, index) => index !== selectedRowIndex
        );

        setEventRows(updatedRows);

        setOpenDeleteDialog(false);

        handleCloseMenu();
    };

    const handleOpenSourceDialog = (index) => {
        setSelectedSourceRowIndex(index);
        setOpenSourceDialog(true);
    };

    const handleSourcePercentageChange = (
        product,
        value
    ) => {
        const updatedRows = [...eventRows];

        updatedRows[selectedSourceRowIndex]
            .source_percentages[product] =
            Number(value || 0);

        setEventRows(updatedRows);
    };

    const sourceTotal =
        selectedSourceRowIndex !== null
            ? Object.values(
                eventRows[selectedSourceRowIndex]
                    ?.source_percentages || {}
            ).reduce(
                (sum, value) =>
                    sum + Number(value || 0),
                0
            )
            : 0;

    const handleRowChange = (
        index,
        field,
        value
    ) => {
        const updatedRows = [...eventRows];

        updatedRows[index] = {
            ...updatedRows[index],
            [field]: value,
        };

        setEventRows(updatedRows);
    };

    const handleRunCalculation = async () => {
        const payload = {
            ta_name: therapyArea,
            indication,
            scenario_name: selectedScenario,

            events: eventRows.map((row) => ({
                event_name: row.event_name,
                lot: row.lot,
                target_product: row.target_product,
                source_percentages: Object.fromEntries(
                    Object.entries(row.source_percentages).map(
                        ([key, value]) => [
                            key,
                            Number(value || 0),
                        ]
                    )
                ),
                start_date: row.start_date,

                curve_type: row.curve_type,

                // start_percent: Number(row.start_percent || 0),
                peak_percent: Number(row.peak_percent || 0),
                duration_months: Number(row.months || 0),
                k_value: Number(row.factor || 0),
            })),
        };

        console.log("========== RUN CALCULATION PAYLOAD ==========");
        console.log(payload);

        console.log(
            "Payload JSON:",
            JSON.stringify(payload, null, 2)
        );

        // future API call
        // runCalculation(payload);
        try {
            const response = await runMarketEventCalculation(payload);
            const data = response?.data;

            console.log("RUN CALCULATION RESPONSE", data);

            // update chart
            setMarketShareChartData(data?.metrics_data?.market_share?.chart || null)

            // update table
            setMarketEventMetricsData(data?.metrics_data || null)

        } catch (error) {
            console.error("Run calculation failed", error);
        }
    };

    const createEmptySourcePercentages = () => {
        return sourceOptions.reduce((acc, source) => {
            acc[source] = "";
            return acc;
        }, {});
    };

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
                    <Box>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "14px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
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
                                minWidth: "140px",
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

                    <Box>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "14px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
                            INDICATION
                        </Typography>

                        <FormControl sx={inputStyle}>
                            <Select
                                value={indication}
                                onChange={(e) => {
                                    setIndication(e.target.value);
                                    setSelectedScenario("");
                                }}
                                displayEmpty
                            >
                                <MenuItem value="" disabled>
                                    Select Indication
                                </MenuItem>

                                {filterOptions.indications.map((item) => (
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

                    <Box>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "14px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
                            SCENARIO SELECTOR
                        </Typography>

                        <FormControl
                            size="small"
                            sx={{
                                minWidth: 180,
                                "& .MuiOutlinedInput-root": {
                                    height: "36px",
                                    borderRadius: "8px",
                                    backgroundColor: "#fff",
                                },
                            }}
                        >
                            <Select
                                value={selectedScenario}
                                onChange={(e) =>
                                    setSelectedScenario(e.target.value)
                                }
                                displayEmpty
                                disabled={!indication}
                            >
                                <MenuItem value="" disabled>
                                    Select Scenario
                                </MenuItem>
                                {availableScenarios.map((scenario) => (
                                    <MenuItem
                                        key={scenario}
                                        value={scenario}
                                    >
                                        {scenario}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* Apply Filter */}
                    <Box sx={{ ml: 2 }}>
                        <Button
                            variant="contained"
                            onClick={handleApplyFilter}
                            sx={{
                                textTransform: "none",
                                borderRadius: "8px",
                                backgroundColor: "#4F46E5",
                                height: "35px",
                            }}
                        >
                            Apply Filter
                        </Button>
                    </Box>
                </Box>
                <Accordion
                    defaultExpanded
                    sx={{
                        mt: 3,
                        borderRadius: "12px !important",
                        border: "1px solid #D8DEE8",
                        boxShadow: "none",
                        overflow: "hidden",
                        "&:before": {
                            display: "none",
                        },
                    }}
                >
                    <AccordionSummary
                        expandIcon={<ExpandMoreIcon />}
                        sx={{
                            px: 3,
                            py: 1,

                            "& .MuiAccordionSummary-content": {
                                margin: 0,
                            },
                        }}
                    >
                        <Box
                            sx={{
                                width: "100%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                flexWrap: "wrap",
                                gap: 2,
                            }}
                        >
                            {/* Left */}
                            <Typography
                                sx={{
                                    fontSize: "14px",
                                    fontWeight: 700,
                                    color: "#475569",
                                    textTransform: "uppercase",
                                }}
                            >
                                Impact Curve Configuration
                            </Typography>

                            {/* Right */}
                            <Box>
                                <Button
                                    variant="contained"
                                    disabled={!marketShareChartData}
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
                                    disabled={!marketShareChartData}
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

                    <AccordionDetails
                        sx={{
                            px: 3,
                            pb: 3,
                            pt: 1,
                        }}
                    >
                        {/* TABLE */}
                        <Paper
                            sx={{
                                mt: 1,
                                border: "1px solid #D8DEE8",
                                borderRadius: "12px",
                                overflowX: "auto",
                                overflowY: "auto",
                                maxHeight: "340px",
                                boxShadow: "none",
                            }}
                        >
                            {/* Header */}
                            <Box
                                sx={{
                                    display: "grid",
                                    gridTemplateColumns:
                                        "0.8fr 0.4fr 0.7fr 0.5fr 0.7fr 0.3fr 0.3fr 0.5fr 1.1fr 40px",
                                    gap: 2,
                                    px: 2,
                                    py: 1.5,
                                    backgroundColor: "#f8fafc",
                                    borderBottom: "1px solid #D8DEE8",
                                    minWidth: "1400px",
                                }}
                            >
                                {[
                                    "Event Name",
                                    "LOT",
                                    "Target Product",
                                    "Source",
                                    "Start Date",
                                    "Peak %",
                                    "Months",
                                    "Curve",
                                    "Factor",
                                    "",
                                ].map((header) => (
                                    <Typography
                                        key={header}
                                        sx={{
                                            fontSize: "13px",
                                            fontWeight: 700,
                                            color: "#64748b",
                                        }}
                                    >
                                        {header}
                                    </Typography>
                                ))}
                            </Box>

                            {/* Rows */}
                            {eventRows.length === 0 ? (
                                <Box
                                    sx={{
                                        p: 2,
                                        textAlign: "center",
                                        color: "#94a3b8",
                                    }}
                                >
                                    Please apply filters to configure events.
                                </Box>
                            ) : (
                                eventRows.map((row, index) => (
                                    <Box
                                        key={index}
                                        sx={{
                                            display: "grid",
                                            gridTemplateColumns:
                                                "0.8fr 0.4fr 0.7fr 0.5fr 0.7fr 0.3fr 0.3fr 0.5fr 1.1fr 40px",
                                            gap: 2,
                                            px: 2,
                                            py: 1.5,
                                            alignItems: "center",
                                            minWidth: "1400px",
                                        }}
                                    >
                                        {/* Event Name */}
                                        <TextField
                                            value={row.event_name}
                                            onChange={(e) =>
                                                handleRowChange(
                                                    index,
                                                    "event_name",
                                                    e.target.value
                                                )
                                            }
                                            size="small"
                                            placeholder="e.g. Growth Initiative"
                                            sx={tableInputStyle}
                                        />

                                        <FormControl size="small">
                                            <Select
                                                value={row.lot}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "lot",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    borderRadius: "6px",
                                                    height: "32px",
                                                    fontSize: "13px",
                                                }}
                                            >
                                                {lots.map((item) => (
                                                    <MenuItem
                                                        key={item}
                                                        value={item}
                                                    >
                                                        {item}
                                                    </MenuItem>
                                                ))}
                                            </Select>
                                        </FormControl>

                                        <FormControl size="small">
                                            <Select
                                                value={row.target_product}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "target_product",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    borderRadius: "6px",
                                                    height: "32px",
                                                    fontSize: "13px",
                                                }}
                                            >
                                                {targetProducts.map((item) => (
                                                    <MenuItem
                                                        key={item}
                                                        value={item}
                                                    >
                                                        {item}
                                                    </MenuItem>
                                                ))}
                                            </Select>
                                        </FormControl>

                                        {/* Source */}
                                        <Button
                                            variant="outlined"
                                            onClick={() =>
                                                handleOpenSourceDialog(index)
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

                                        {/* Start Date */}
                                        <LocalizationProvider dateAdapter={AdapterDayjs}>
                                            <DatePicker
                                                value={
                                                    row.start_date
                                                        ? dayjs(row.start_date)
                                                        : null
                                                }
                                                onChange={(newValue) =>
                                                    handleRowChange(
                                                        index,
                                                        "start_date",
                                                        newValue
                                                            ? newValue.format("YYYY-MM-DD")
                                                            : ""
                                                    )
                                                }
                                                format="DD-MM-YYYY"
                                                slotProps={{
                                                    textField: {
                                                        size: "small",
                                                        sx: tableInputStyle,
                                                    },
                                                }}
                                            />
                                        </LocalizationProvider>

                                        {/* Peak % */}
                                        <TextField
                                            value={row.peak_percent}
                                            size="small"
                                            placeholder="e.g. 1"
                                            onChange={(e) =>
                                                handleRowChange(
                                                    index,
                                                    "peak_percent",
                                                    e.target.value
                                                )
                                            }
                                            sx={tableInputStyle}
                                        />

                                        {/* Months */}
                                        <TextField
                                            value={row.months}
                                            onChange={(e) =>
                                                handleRowChange(
                                                    index,
                                                    "months",
                                                    e.target.value
                                                )
                                            }
                                            size="small"
                                            placeholder="e.g. 6"
                                            sx={tableInputStyle}
                                        />

                                        {/* Curve */}
                                        <FormControl size="small">
                                            <Select
                                                value={row.curve_type}
                                                onChange={(e) =>
                                                    handleRowChange(
                                                        index,
                                                        "curve_type",
                                                        e.target.value
                                                    )
                                                }
                                                sx={{
                                                    borderRadius: "6px",
                                                    height: "32px",
                                                    fontSize: "13px",
                                                }}
                                            >
                                                {curveTypes.map((item) => (
                                                    <MenuItem
                                                        key={item}
                                                        value={item}
                                                    >
                                                        {item}
                                                    </MenuItem>
                                                ))}
                                            </Select>
                                        </FormControl>

                                        {/* Factor */}
                                        <TextField
                                            value={row.factor}
                                            onChange={(e) =>
                                                handleRowChange(
                                                    index,
                                                    "factor",
                                                    e.target.value
                                                )
                                            }
                                            size="small"
                                            placeholder="e.g. 1"
                                            sx={tableInputStyle}
                                        />

                                        {/* 3 dots */}
                                        <Box
                                            sx={{
                                                display: "flex",
                                                justifyContent: "center",
                                                cursor: "pointer",
                                                color: "#64748b",
                                            }}
                                            onClick={(event) =>
                                                handleOpenMenu(event, index)
                                            }
                                        >
                                            <MoreVertIcon fontSize="small" />
                                        </Box>
                                    </Box>
                                ))
                            )}
                            < Menu
                                anchorEl={menuAnchorEl}
                                open={Boolean(menuAnchorEl)}
                                onClose={handleCloseMenu}
                            >
                                <DropdownMenuItem
                                    onClick={handleDuplicateRow}
                                >
                                    Duplicate
                                </DropdownMenuItem>

                                <DropdownMenuItem
                                    onClick={() => {
                                        setOpenDeleteDialog(true);
                                    }}
                                    sx={{
                                        color: "red",
                                    }}
                                >
                                    Delete
                                </DropdownMenuItem>
                            </Menu>
                            {/* delete dialog */}
                            <Dialog
                                open={openDeleteDialog}
                                onClose={() => setOpenDeleteDialog(false)}
                            >
                                <DialogTitle
                                    sx={{
                                        color: "#ef4444",
                                        fontWeight: 700,
                                    }}
                                >
                                    Delete Event?
                                </DialogTitle>

                                <DialogContent>
                                    <DialogContentText>
                                        Are you sure you want to remove this
                                        event? This action cannot be undone.
                                    </DialogContentText>
                                </DialogContent>

                                <DialogActions sx={{ pb: 2, pr: 3 }}>
                                    <Button
                                        onClick={() =>
                                            setOpenDeleteDialog(false)
                                        }
                                        variant="outlined"
                                        sx={{
                                            textTransform: "none",
                                        }}
                                    >
                                        Cancel
                                    </Button>

                                    <Button
                                        onClick={handleDeleteRow}
                                        variant="contained"
                                        color="error"
                                        sx={{
                                            textTransform: "none",
                                        }}
                                    >
                                        Delete
                                    </Button>
                                </DialogActions>
                            </Dialog>

                            {/* source dialog */}
                            <Dialog
                                open={openSourceDialog}
                                onClose={() => setOpenSourceDialog(false)}
                                PaperProps={{
                                    sx: {
                                        width: "300px",
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
                                    Source of Business (%)

                                    <IconButton
                                        onClick={() => setOpenSourceDialog(false)}
                                        size="small"
                                    >
                                        <CloseIcon fontSize="small" />
                                    </IconButton>
                                </DialogTitle>

                                <DialogContent>
                                    <Box
                                        sx={{
                                            mt: 1,
                                            display: "flex",
                                            flexDirection: "column",
                                            gap: 2,
                                        }}
                                    >
                                        {selectedSourceRowIndex !== null &&
                                            Object.entries(
                                                eventRows[selectedSourceRowIndex]
                                                    ?.source_percentages || {}
                                            ).map(([product, value]) => (
                                                <Box
                                                    key={product}
                                                    sx={{
                                                        display: "flex",
                                                        alignItems: "center",
                                                        gap: 9,
                                                    }}
                                                >
                                                    <Typography sx={{ fontSize: '14px', width: '120px', flexShrink: 0 }}>
                                                        {product}
                                                    </Typography>

                                                    <TextField
                                                        type="number"
                                                        value={value}
                                                        onChange={(e) =>
                                                            handleSourcePercentageChange(
                                                                product,
                                                                e.target.value
                                                            )
                                                        }
                                                        size="small"
                                                        sx={{
                                                            width: "60px",

                                                            "& .MuiOutlinedInput-root": {
                                                                height: "30px",
                                                                fontSize: "13px",
                                                            },

                                                            "& input": {
                                                                padding: "6px 8px",
                                                            },
                                                        }}
                                                    />
                                                </Box>
                                            ))}

                                        {/* <Typography
                                        sx={{
                                            mt: 1,
                                            fontWeight: 600,
                                            color:
                                                sourceTotal === 100
                                                    ? "#16a34a"
                                                    : "#ef4444",
                                        }}
                                    >
                                        Total: {sourceTotal}%
                                    </Typography> */}
                                        {sourceTotal !== 100 && (
                                            <Typography
                                                sx={{
                                                    fontSize: "12px",
                                                    color: "#ef4444",
                                                }}
                                            >
                                                Total must equal 100%
                                            </Typography>
                                        )}
                                    </Box>
                                </DialogContent>

                                <DialogActions
                                    sx={{
                                        p: 3,
                                        pt: 1,
                                    }}
                                >
                                    <Button
                                        fullWidth
                                        variant="contained"
                                        disabled={sourceTotal !== 100}
                                        onClick={() =>
                                            setOpenSourceDialog(false)
                                        }
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
                            </Dialog>
                        </Paper>

                        {/* </Paper> */}
                        <MarketEventChart chartData={marketShareChartData} />
                    </AccordionDetails>
                </Accordion>
                <MarketEventOutputTable
                    metricsData={marketEventMetricsData}
                    months={
                        marketShareChartData?.months || []
                    }
                    therapyArea={therapyArea}
                    indication={indication}
                    selectedScenario={selectedScenario}
                    setMarketShareChartData={
                        setMarketShareChartData
                    }
                    setMarketEventMetricsData={
                        setMarketEventMetricsData
                    }
                />
            </Paper>
        </Box >
    );
}