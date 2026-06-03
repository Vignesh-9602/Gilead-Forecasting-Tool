import React, { useContext, useState, useEffect } from "react";

import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    Button,
    Checkbox,
    ListItemText,
} from "@mui/material";

import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";

import dayjs from "dayjs";

import { GlobalContext } from "../../../context/Provider";

import PersistencyTable from "./PersistencyTable";

import { getPersistencyFilters, applyPersistencyFilters } from "../../../services/apiService";
import { useSnackbarStore, useLoadingStore } from "../../../stores";

const metricOptions = [
    {
        label: "Overall Market Volume",
        value: "nps",
    },
    {
        label: "Market Share",
        value: "market_share",
    },
];

const vialCalculatorDateLocaleText = {
    fieldMonthPlaceholder: () => "MM",
};

export default function VialCalculator() {

    const { favState } = useContext(GlobalContext);

    const therapyArea = favState?.selectedTherapyArea;

    const [indication, setIndication] = useState("");
    const [metric, setMetric] = useState("");
    const [lots, setLots] = useState([]);
    const [brand, setBrand] = useState("");
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");

    const [mappingData, setMappingData] = useState({});
    const [scenarioSelector, setScenarioSelector] = useState("");

    const [filterOptions, setFilterOptions] = useState({
        scenario_names: [],
        indications: [],
    });

    const [loadingFilters, setLoadingFilters] = useState(false);

    const [persistencyData, setPersistencyData] = useState(null);

    const { showSnackbar } = useSnackbarStore();
    const { setLoading, isLoading } = useLoadingStore();

    const [filterApplyVersion, setFilterApplyVersion] = useState(0);

    const isApplyFilterEnabled =
        !!therapyArea &&
        !!scenarioSelector &&
        !!indication &&
        lots.length > 0 &&
        !!brand &&
        !!startDate &&
        !!endDate;

    useEffect(() => {
        if (therapyArea) {
            fetchPersistencyFilters();
        }
    }, [therapyArea]);

    const fetchPersistencyFilters = async () => {
        try {
            setLoading(true);

            const response = await getPersistencyFilters(
                therapyArea
            );

            const resData = response?.data;

            setMappingData(resData?.data || {});

            const defaultFilter =
                resData?.default_filter;

            if (defaultFilter) {
                setScenarioSelector(
                    defaultFilter.scenario_name
                );

                setIndication(
                    defaultFilter.indication
                );

                setLots(
                    defaultFilter.lots || []
                );

                setBrand(
                    defaultFilter.brand || ""
                );

                setStartDate(
                    defaultFilter.start_date || ""
                );

                setEndDate(
                    defaultFilter.end_date || ""
                );

                setFilterOptions({
                    scenario_names:
                        resData?.scenario_names || [],

                    indications: Object.keys(
                        resData?.data?.[
                        defaultFilter.scenario_name
                        ] || {}
                    ),
                });

                setTimeout(() => {
                    setBrand(
                        defaultFilter.brand || ""
                    );
                }, 0);

                // Auto Apply Filter
                const payload = {
                    ta_name: therapyArea,
                    scenario_name:
                        defaultFilter.scenario_name,
                    indication:
                        defaultFilter.indication,
                    lots:
                        defaultFilter.lots || [],
                    brand:
                        defaultFilter.brand || "",
                    start_date:
                        defaultFilter.start_date,
                    end_date:
                        defaultFilter.end_date,
                };

                // setLoading(true);

                const applyResponse =
                    await applyPersistencyFilters(
                        payload
                    );

                setPersistencyData(
                    applyResponse?.data || null
                );

                setFilterApplyVersion(
                    (prev) => prev + 1
                );

                // showSnackbar(
                //     "Filters applied successfully",
                //     "success"
                // );
            } else {
                setFilterOptions({
                    scenario_names:
                        resData?.scenario_names || [],
                    indications: [],
                });
            }
        } catch (error) {
            console.error(
                "Failed to fetch persistency filters",
                error
            );

            showSnackbar(
                "Failed to fetch persistency filters",
                "error"
            );
        } finally {
            // setLoadingFilters(false);
            setLoading(false);
        }
    };

    // ------------------------------------
    // DYNAMIC OPTIONS
    // ------------------------------------
    const indicationOptions =
        scenarioSelector
            ? Object.keys(
                mappingData?.[scenarioSelector] || {}
            )
            : [];

    const lotOptions =
        scenarioSelector && indication
            ? Object.keys(
                mappingData?.[scenarioSelector]?.[indication] || {}
            )
            : [];

    const brandOptions =
        scenarioSelector && indication
            ? [
                ...new Set(
                    Object.values(
                        mappingData?.[scenarioSelector]?.[indication] || {}
                    ).flat()
                ),
            ]
            : [];

    // ------------------------------------
    // RESET DEPENDENCIES
    // ------------------------------------
    useEffect(() => {
        setIndication("");
        setLots([]);
        setBrand("");
    }, [scenarioSelector]);

    useEffect(() => {
        setLots([]);
        setBrand("");
    }, [indication]);

    useEffect(() => {
        if (indication && lotOptions.length > 0) {
            setLots(lotOptions);
        }
    }, [indication, mappingData]);

    // ------------------------------------
    // STYLES
    // ------------------------------------
    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "160px",

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

    const handleApplyFilter = async () => {
        try {
            setLoading(true);
            const payload = {
                ta_name: therapyArea,
                scenario_name: scenarioSelector,
                indication,
                lots,
                brand,
                start_date: startDate,
                end_date: endDate,
            };
            const response = await applyPersistencyFilters(payload);
            setPersistencyData(response?.data || null);
            setFilterApplyVersion(prev => prev + 1);
            showSnackbar("Filters applied successfully", "success");
        } catch (error) {
            console.error("Failed to apply persistency filters", error);
            showSnackbar("Failed to apply persistency filter", "error");
        } finally {
            setLoading(false);
        }
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
                                minWidth: "120px",
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

                    {/* SCENARIO */}
                    <Box>
                        <Typography sx={labelStyle}>
                            SCENARIO
                        </Typography>

                        <FormControl sx={inputStyle}>
                            <Select
                                value={scenarioSelector}
                                onChange={(e) => {
                                    const selectedScenario = e.target.value;

                                    setScenarioSelector(selectedScenario);

                                    setIndication("");
                                    setLots([]);
                                    setBrand("");

                                    setFilterOptions((prev) => ({
                                        ...prev,
                                        indications: Object.keys(
                                            mappingData?.[selectedScenario] || {}
                                        ),
                                    }));
                                }}
                                displayEmpty
                            >
                                <MenuItem value="" disabled>
                                    Select Scenario
                                </MenuItem>

                                {filterOptions.scenario_names.map((scenario) => (
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

                    {/* INDICATION */}
                    <Box>
                        <Typography sx={labelStyle}>
                            INDICATION
                        </Typography>
                        <FormControl sx={inputStyle}>

                            <Select
                                value={indication}
                                disabled={!scenarioSelector}
                                onChange={(e) =>
                                    setIndication(
                                        e.target.value
                                    )
                                }
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


                    {/* LOT */}
                    <Box>

                        <Typography sx={labelStyle}>
                            LOT
                        </Typography>

                        <FormControl
                            sx={inputStyle}
                            disabled={!indication}
                        >

                            <Select
                                multiple
                                value={lots}
                                onChange={(e) => {
                                    const value = e.target.value;

                                    // Select All clicked
                                    if (value.includes("SELECT_ALL")) {
                                        if (lots.length === lotOptions.length) {
                                            setLots([]);
                                        } else {
                                            setLots(lotOptions);
                                        }
                                    } else {
                                        setLots(value);
                                    }
                                }}
                                displayEmpty
                                renderValue={(selected) =>
                                    selected.length === 0
                                        ? "Select Lots"
                                        : selected.join(", ")
                                }
                            >
                                {/* Select All */}
                                <MenuItem value="SELECT_ALL">
                                    <Checkbox
                                        checked={
                                            lots.length === lotOptions.length &&
                                            lotOptions.length > 0
                                        }
                                        indeterminate={
                                            lots.length > 0 &&
                                            lots.length < lotOptions.length
                                        }
                                    />

                                    <ListItemText
                                        primary="Select All"
                                    />
                                </MenuItem>

                                {/* LOT OPTIONS */}
                                {lotOptions.map((item) => (
                                    <MenuItem
                                        key={item}
                                        value={item}
                                    >
                                        <Checkbox
                                            checked={lots.includes(item)}
                                        />

                                        <ListItemText
                                            primary={item}
                                        />
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* PRODUCT */}
                    <Box>
                        <Typography sx={labelStyle}>
                            PRODUCT
                        </Typography>

                        <FormControl sx={inputStyle} >
                            <Select
                                value={brand}
                                // disabled={!lots}
                                onChange={(e) =>
                                    setBrand(
                                        e.target.value
                                    )
                                }
                                displayEmpty
                            >
                                <MenuItem value="" disabled>
                                    Select Product
                                </MenuItem>

                                {brandOptions.map((item) => (
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

                    {/* START DATE */}
                    <Box sx={{ minWidth: "150px" }}>
                        <Typography sx={labelStyle}>
                            START DATE
                        </Typography>
                        <LocalizationProvider
                            dateAdapter={AdapterDayjs}
                            localeText={vialCalculatorDateLocaleText}
                        >
                            <DatePicker
                                value={
                                    startDate
                                        ? dayjs(startDate)
                                        : null
                                }
                                onChange={(newValue) =>
                                    setStartDate(
                                        newValue
                                            ? newValue.format(
                                                "YYYY-MM-DD"
                                            )
                                            : ""
                                    )
                                }
                                format="DD-MMM-YYYY"
                                slotProps={{
                                    textField: {
                                        size: "small",
                                        placeholder: "DD-MMM-YYYY",
                                        sx: {
                                            ...inputStyle,
                                            width: "140px",
                                            "& .MuiInputBase-input": {
                                                color:
                                                    startDate
                                                        ? "#000"
                                                        : "transparent",

                                                caretColor:
                                                    "transparent",
                                            },
                                        },
                                        fullWidth: true,
                                    },
                                }}
                            />
                        </LocalizationProvider>
                    </Box>

                    {/* END DATE */}
                    <Box sx={{ minWidth: "150px" }}>
                        <Typography sx={labelStyle}>
                            END DATE
                        </Typography>
                        <LocalizationProvider
                            dateAdapter={AdapterDayjs}
                            localeText={vialCalculatorDateLocaleText}
                        >
                            <DatePicker
                                value={
                                    endDate
                                        ? dayjs(endDate)
                                        : null
                                }
                                onChange={(newValue) =>
                                    setEndDate(
                                        newValue
                                            ? newValue.format(
                                                "YYYY-MM-DD"
                                            )
                                            : ""
                                    )
                                }
                                format="DD-MMM-YYYY"
                                slotProps={{
                                    textField: {
                                        size: "small",
                                        placeholder: "DD-MMM-YYYY",
                                        sx: {
                                            ...inputStyle,
                                            width: "140px",
                                            "& .MuiInputBase-input": {
                                                color:
                                                    endDate
                                                        ? "#000"
                                                        : "transparent",

                                                caretColor:
                                                    "transparent",
                                            },
                                        },

                                        fullWidth: true,
                                    },
                                }}
                            />

                        </LocalizationProvider>
                    </Box>

                    {/* APPLY FILTER */}
                    <Button
                        variant="contained"
                        onClick={handleApplyFilter}
                        // disabled={loadingFilters}
                        disabled={!isApplyFilterEnabled}
                        sx={{ height: "40px", px: 3, borderRadius: "8px", textTransform: "none", backgroundColor: "#4F46E5" }}
                    >
                        Apply Filter
                    </Button>

                </Box>

                <PersistencyTable
                    persistencyData={persistencyData}
                    setPersistencyData={setPersistencyData}
                    loading={isLoading}
                    therapyArea={therapyArea}
                    indication={indication}
                    brand={brand}
                    startDate={startDate}
                    endDate={endDate}
                    lots={lots}
                    scenarioSelector={scenarioSelector}
                    showSnackbar={showSnackbar}
                    filterApplyVersion={filterApplyVersion}
                />

            </Paper >
        </Box >
    );
}