import React, { useContext, useEffect, useState } from "react";
import { Box, Paper, Typography, FormControl, Select, MenuItem, Button, Tab, Tabs, Checkbox, ListItemText } from "@mui/material";
import dayjs from "dayjs";
import { GlobalContext } from "../../../context/Provider";
import OutputChart from "./OutputChart";
import OutputTable from "./OutputTable";
import { getOutputFilters, applyOutputFilters } from "../../../services/apiService";

import { useSnackbarStore, useLoadingStore, } from "../../../stores";

export default function Output() {
    const { favState } = useContext(GlobalContext);

    const therapyArea = favState?.selectedTherapyArea;

    const { showSnackbar } = useSnackbarStore();

    const { setLoading } = useLoadingStore();

    const [mappingData, setMappingData] = useState({});

    const [availableMonths, setAvailableMonths] = useState([]);

    const [scenarioOptions, setScenarioOptions] = useState([]);

    const [scenario, setScenario] = useState("");

    const [indications, setIndications] =
        useState([]);

    const [lots, setLots] =
        useState([]);

    const [products, setProducts] =
        useState([]);

    const [startDate, setStartDate] = useState("");

    const [endDate, setEndDate] = useState("");

    const [outputData, setOutputData] = useState(null);

    // const [chartData, setChartData] = useState(null);
    const [activeTab, setActiveTab] =
        useState("indication");

    useEffect(() => {
        if (therapyArea) {
            fetchFilters();
        }
    }, [therapyArea]);

    const fetchFilters = async () => {
        try {
            setLoading(true);

            const response = await getOutputFilters(therapyArea);

            const resData = response?.data;

            setMappingData(resData?.data || {});

            setScenarioOptions(
                resData?.scenario_names || []
            );

            setAvailableMonths(
                resData?.available_months || []
            );

            const defaultFilter =
                resData?.selected_filter;

            if (defaultFilter) {
                const defaultScenario =
                    defaultFilter.scenario_name;

                const defaultIndication =
                    defaultFilter.indication;

                const defaultLot =
                    defaultFilter?.lots?.[0] || "";

                const defaultProduct =
                    defaultFilter.brand;

                setScenario(defaultScenario);
                setIndications(
                    defaultFilter.indications || []
                );

                setLots(
                    defaultFilter.lots || []
                );

                setProducts(
                    defaultFilter.brands || []
                );
                setStartDate(defaultFilter.start_date);
                setEndDate(defaultFilter.end_date);

                // Auto-load chart + table on page load

                const payload = {
                    ta_name: therapyArea,
                    scenario_name: defaultScenario,
                    indications:
                        defaultFilter.indications || [],

                    lots:
                        defaultFilter.lots || [],

                    brands:
                        defaultFilter.brands || [],
                    start_date: defaultFilter.start_date,
                    end_date: defaultFilter.end_date,
                };

                const applyResponse =
                    await applyOutputFilters(payload);

                const applyData =
                    applyResponse?.data;

                setOutputData(applyData);

                // setChartData(
                //     applyData?.chart || null
                // );
            }
        } catch (error) {
            console.error(error);

            showSnackbar(
                "Failed to load filters",
                "error"
            );
        } finally {
            setLoading(false);
        }
    };

    const indicationOptions = scenario
        ? Object.keys(mappingData?.[scenario] ?? {})
        : [];

    const lotOptions =
        scenario &&
            indications.length > 0
            ? [
                ...new Set(
                    indications.flatMap(
                        (indication) =>
                            Object.keys(
                                mappingData?.[
                                scenario
                                ]?.[
                                indication
                                ] || {}
                            )
                    )
                ),
            ]
            : [];

    const productOptions =
        scenario &&
            indications.length > 0
            ? [
                ...new Set(
                    indications.flatMap(
                        (indication) =>
                            Object.values(
                                mappingData?.[
                                scenario
                                ]?.[
                                indication
                                ] || {}
                            ).flat()
                    )
                ),
            ]
            : [];

    const handleApplyFilter = async () => {
        try {
            setLoading(true);

            const payload = {
                ta_name: therapyArea,

                scenario_name: scenario,

                indications,

                lots,

                brands: products,

                start_date: startDate,

                end_date: endDate,
            };

            const response =
                await applyOutputFilters(payload);

            const resData = response?.data;

            setOutputData(resData);

            // setChartData(resData?.chart || null);

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

    const labelStyle = {
        mb: 1,
        fontSize: "14px",
        fontWeight: 700,
        color: "#64748b",
    };

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

    const currentView =
        outputData?.views?.[activeTab];

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
                    {/* THERAPEUTIC AREA */}
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
                                value={scenario}
                                displayEmpty
                                onChange={(e) => {
                                    const value = e.target.value;

                                    setScenario(value);
                                    setIndications([]);
                                    setLots([]);
                                    setProducts([]);
                                }}
                            >
                                <MenuItem value="" disabled>
                                    Select Scenario
                                </MenuItem>
                                {scenarioOptions.map((item) => (
                                    <MenuItem key={item} value={item}>
                                        {item}
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

                        <FormControl sx={{ ...inputStyle, maxWidth: 180 }}>
                            <Select
                                multiple
                                value={indications}
                                disabled={!scenario}
                                displayEmpty
                                onChange={(e) => {

                                    const value =
                                        e.target.value;

                                    if (
                                        value.includes(
                                            "SELECT_ALL"
                                        )
                                    ) {
                                        setIndications(
                                            indications.length ===
                                                indicationOptions.length
                                                ? []
                                                : indicationOptions
                                        );
                                    } else {
                                        setIndications(value);
                                    }

                                    setLots([]);
                                    setProducts([]);
                                }}
                                renderValue={(selected) =>
                                    selected.length
                                        ? selected.join(", ")
                                        : "Select Indication"
                                }
                            >
                                <MenuItem value="SELECT_ALL">
                                    <Checkbox
                                        checked={
                                            indications.length ===
                                            indicationOptions.length &&
                                            indicationOptions.length > 0
                                        }
                                        indeterminate={
                                            indications.length > 0 &&
                                            indications.length <
                                            indicationOptions.length
                                        }
                                    />
                                    <ListItemText primary="Select All" />
                                </MenuItem>

                                {indicationOptions.map(
                                    (option) => (
                                        <MenuItem
                                            key={option}
                                            value={option}
                                        >
                                            <Checkbox
                                                checked={indications.includes(
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
                    </Box>

                    {/* LOT */}
                    <Box>
                        <Typography sx={labelStyle}>
                            LOT
                        </Typography>

                        <FormControl sx={{ ...inputStyle, maxWidth: 180 }}>
                            <Select
                                multiple
                                value={lots}
                                disabled={
                                    indications.length === 0
                                }
                                displayEmpty
                                onChange={(e) => {

                                    const value =
                                        e.target.value;

                                    if (
                                        value.includes(
                                            "SELECT_ALL"
                                        )
                                    ) {
                                        setLots(
                                            lots.length ===
                                                lotOptions.length
                                                ? []
                                                : lotOptions
                                        );
                                    } else {
                                        setLots(value);
                                    }

                                    setProducts([]);
                                }}
                                renderValue={(selected) =>
                                    selected.length
                                        ? selected.join(", ")
                                        : "Select LOT"
                                }
                            >
                                <MenuItem value="SELECT_ALL">
                                    <Checkbox
                                        checked={
                                            lots.length ===
                                            lotOptions.length &&
                                            lotOptions.length > 0
                                        }
                                        indeterminate={
                                            lots.length > 0 &&
                                            lots.length <
                                            lotOptions.length
                                        }
                                    />
                                    <ListItemText primary="Select All" />
                                </MenuItem>

                                {lotOptions.map((option) => (
                                    <MenuItem
                                        key={option}
                                        value={option}
                                    >
                                        <Checkbox
                                            checked={lots.includes(
                                                option
                                            )}
                                        />
                                        <ListItemText
                                            primary={option}
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

                        <FormControl sx={{ ...inputStyle, maxWidth: 180 }}>
                            <Select
                                multiple
                                value={products}
                                disabled={
                                    lots.length === 0
                                }
                                displayEmpty
                                onChange={(e) => {

                                    const value =
                                        e.target.value;

                                    if (
                                        value.includes(
                                            "SELECT_ALL"
                                        )
                                    ) {
                                        setProducts(
                                            products.length ===
                                                productOptions.length
                                                ? []
                                                : productOptions
                                        );
                                    } else {
                                        setProducts(value);
                                    }
                                }}
                                renderValue={(selected) =>
                                    selected.length
                                        ? selected.join(", ")
                                        : "Select Product"
                                }
                            >
                                <MenuItem value="SELECT_ALL">
                                    <Checkbox
                                        checked={
                                            products.length ===
                                            productOptions.length &&
                                            productOptions.length > 0
                                        }
                                        indeterminate={
                                            products.length > 0 &&
                                            products.length <
                                            productOptions.length
                                        }
                                    />
                                    <ListItemText primary="Select All" />
                                </MenuItem>

                                {productOptions.map(
                                    (option) => (
                                        <MenuItem
                                            key={option}
                                            value={option}
                                        >
                                            <Checkbox
                                                checked={products.includes(
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
                    </Box>

                    {/* START DATE */}
                    <Box>
                        <Typography sx={labelStyle}>
                            START DATE
                        </Typography>

                        <FormControl sx={inputStyle}>
                            <Select
                                value={startDate}
                                onChange={(e) => {
                                    const value = e.target.value;

                                    setStartDate(value);
                                }}
                                MenuProps={{
                                    PaperProps: {
                                        sx: {
                                            maxHeight: 300,
                                            width: 130,
                                        },
                                    },
                                }}
                            >
                                {availableMonths.map((month) => (
                                    <MenuItem key={month} value={month}>
                                        {dayjs(month).format("MMM YY")}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* END DATE */}
                    <Box>
                        <Typography sx={labelStyle}>
                            END DATE
                        </Typography>

                        <FormControl sx={inputStyle}>
                            <Select
                                value={endDate}
                                onChange={(e) => {
                                    const value = e.target.value;

                                    setEndDate(value);
                                }}
                                MenuProps={{
                                    PaperProps: {
                                        sx: {
                                            maxHeight: 300,
                                            width: 130,
                                        },
                                    },
                                }}
                            >
                                {availableMonths
                                    .filter(
                                        (month) =>
                                            dayjs(month).isAfter(startDate)
                                    )
                                    .map((month) => (
                                        <MenuItem key={month} value={month}>
                                            {dayjs(month).format("MMM YY")}
                                        </MenuItem>
                                    ))}
                            </Select>
                        </FormControl>
                    </Box>

                    <Button
                        variant="contained"
                        onClick={handleApplyFilter}
                        sx={{
                            height: "40px",
                            px: 3,
                            borderRadius: "8px",
                            textTransform: "none",
                            backgroundColor: "#4F46E5",
                        }}
                    >
                        Apply Filter
                    </Button>
                </Box>

                <Box
                    sx={{
                        mt: 3,
                        p: 1,
                        bgcolor: "#E2E8F0",
                        borderRadius: "12px",
                        // display: "inline-flex",
                    }}
                >
                    <Tabs
                        value={activeTab}
                        onChange={(e, value) => setActiveTab(value)}
                        TabIndicatorProps={{
                            style: {
                                display: "none",
                            },
                        }}
                        sx={{
                            minHeight: "40px",

                            "& .MuiTab-root": {
                                textTransform: "none",
                                fontWeight: 600,
                                fontSize: "14px",
                                minHeight: "40px",
                                borderRadius: "10px",
                                color: "#475569",
                                transition: "all 0.2s ease",
                                px: 3,
                            },

                            "& .Mui-selected": {
                                backgroundColor: "#FFFFFF",
                                color: "#2563EB",
                                boxShadow:
                                    "0 1px 3px rgba(0,0,0,0.08)",
                            },
                        }}
                    >
                        <Tab
                            label="Demand Summary by Indication"
                            value="indication"
                        />

                        <Tab
                            label="Demand Summary by LOT"
                            value="lot"
                        />
                    </Tabs>
                </Box>
                {/* 
                <OutputChart chartData={chartData} />
                <OutputTable outputData={outputData} /> */}
                <OutputChart
                    chartData={currentView?.chart}
                />

                <OutputTable
                    tableData={currentView?.table}
                />
            </Paper >
        </Box >
    );
}