import React, { useContext, useEffect, useState } from "react";
import { Box, Paper, Typography, FormControl, Select, MenuItem, Button } from "@mui/material";
import dayjs from "dayjs";
import { GlobalContext } from "../../../context/Provider";

// import { getOutputFilters, applyOutputFilters,} from "../../../services/apiService";

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

    const [indication, setIndication] = useState("");

    const [lot, setLot] = useState("");

    const [product, setProduct] = useState("");

    const [startDate, setStartDate] = useState("");

    const [endDate, setEndDate] = useState("");

    const [outputData, setOutputData] = useState(null);

    useEffect(() => {
        if (therapyArea) {
            fetchFilters();
        }
    }, [therapyArea]);

    const OUTPUT_FILTER_RESPONSE = {
        ta_name: "Oncology",

        scenario_names: [
            "Finalised",
            "BASE",
            "test_01",
        ],

        data: {
            BASE: {
                "mHR+": {
                    "1L": [
                        "Brand 1",
                        "Brand 2",
                        "TPC",
                        "Trodelvy",
                    ],
                    "2L": [
                        "Brand 1",
                        "Brand 2",
                        "TPC",
                        "Trodelvy",
                    ],
                    "3L": [
                        "Brand 1",
                        "Brand 2",
                        "TPC",
                        "Trodelvy",
                    ],
                },

                mTNBC: {
                    "1L": [
                        "Brand 1",
                        "Brand 2",
                        "Competitor 1",
                        "Competitor 2",
                        "TPC",
                        "Trodelvy",
                    ],

                    "2L": [
                        "Brand 1",
                        "Brand 2",
                        "Competitor 1",
                        "Competitor 2",
                        "TPC",
                        "Trodelvy",
                    ],

                    "3L+": [
                        "Brand 1",
                        "Brand 2",
                        "Competitor 1",
                        "Competitor 2",
                        "TPC",
                        "Trodelvy",
                    ],
                },

                mUC: {
                    "1L": [
                        "Brand 1",
                        "TPC",
                        "Trodelvy",
                    ],

                    "2L": [
                        "Brand 1",
                        "TPC",
                        "Trodelvy",
                    ],
                },
            },

            Finalised: {
                mTNBC: {
                    "1L": [
                        "Brand 1",
                        "Brand 2",
                        "Competitor 1",
                        "Competitor 2",
                        "TPC",
                        "Trodelvy",
                    ],

                    "2L": [
                        "Brand 1",
                        "Brand 2",
                        "Competitor 1",
                        "Competitor 2",
                        "TPC",
                        "Trodelvy",
                    ],
                },
            },

            test_01: {
                mTNBC: {
                    "1L": [
                        "Brand 1",
                        "Brand 2",
                        "Competitor 1",
                        "Competitor 2",
                        "TPC",
                        "Trodelvy",
                    ],
                },
            },
        },

        available_months: [
            "2024-01-01",
            "2024-02-01",
            "2024-03-01",
            "2024-04-01",
            "2024-05-01",
            "2024-06-01",
            "2024-07-01",
            "2024-08-01",
            "2024-09-01",
            "2024-10-01",
            "2024-11-01",
            "2024-12-01",
            "2025-01-01",
            "2025-02-01",
            "2025-03-01",
            "2025-04-01",
            "2025-05-01",
            "2025-06-01",
            "2025-07-01",
            "2025-08-01",
            "2025-09-01",
            "2025-10-01",
            "2025-11-01",
            "2025-12-01",
            "2026-01-01",
            "2026-02-01",
            "2026-03-01",
            "2026-04-01",
            "2026-05-01",
            "2026-06-01",
        ],

        selected_filter: {
            scenario_name: "BASE",
            indication: "mTNBC",
            lots: ["1L", "2L", "3L+"],
            brand: "Brand 1",
            start_date: "2025-01-01",
            end_date: "2026-06-01",
        },
    };

    const fetchFilters = async () => {
        try {
            setLoading(true);

            // const response =
            //     await getOutputFilters(
            //         therapyArea
            //     );

            // const resData =
            //     response?.data;

            const resData = OUTPUT_FILTER_RESPONSE;

            setMappingData(resData?.data || {});

            setScenarioOptions(resData?.scenario_names || []);

            setAvailableMonths(resData?.available_months || []);

            const defaultFilter = resData?.selected_filter;

            if (defaultFilter) {
                const defaultScenario = defaultFilter.scenario_name;

                const defaultIndication = defaultFilter.indication;

                const defaultLot = defaultFilter?.lots?.[0] || "";

                const defaultProduct = defaultFilter.brand;

                setScenario(defaultScenario);

                setIndication(defaultIndication);

                setLot(defaultLot);

                setProduct(defaultProduct);

                setStartDate(defaultFilter.start_date);

                setEndDate(defaultFilter.end_date);

                // const payload = {
                //     ta_name: therapyArea,
                //     scenario_name:
                //         defaultScenario,
                //     indication:
                //         defaultIndication,
                //     lot: defaultLot,
                //     product:
                //         defaultProduct,
                //     start_date:
                //         defaultFilter.start_date,
                //     end_date:
                //         defaultFilter.end_date,
                // };

                // const applyResponse =
                //     await applyOutputFilters(
                //         payload
                //     );

                // setOutputData(
                //     applyResponse?.data || null
                // );
            }
        } catch (error) {
            console.error(error);
            showSnackbar("Failed to load filters", "error");
        } finally {
            setLoading(false);
        }
    };

    const indicationOptions = scenario
        ? Object.keys(mappingData?.[scenario] ?? {})
        : [];

    const lotOptions = scenario && indication
        ? Object.keys(mappingData?.[scenario]?.[indication] || {})
        : [];

    const productOptions = scenario && indication && lot
        ? mappingData?.[scenario]?.[indication]?.[lot] || []
        : [];

    // const handleApplyFilter =
    //     async () => {
    //         try {
    //             setLoading(true);

    //             const payload = {
    //                 ta_name:
    //                     therapyArea,
    //                 scenario_name:
    //                     scenario,
    //                 indication,
    //                 lot,
    //                 product,
    //                 start_date:
    //                     startDate,
    //                 end_date:
    //                     endDate,
    //             };

    //             const response =
    //                 await applyOutputFilters(
    //                     payload
    //                 );

    //             setOutputData(
    //                 response?.data || null
    //             );

    //             showSnackbar(
    //                 "Filters applied successfully",
    //                 "success"
    //             );
    //         } catch (error) {
    //             console.error(error);

    //             showSnackbar(
    //                 "Failed to apply filters",
    //                 "error"
    //             );
    //         } finally {
    //             setLoading(false);
    //         }
    //     };

    const handleApplyFilter = () => {
        const payload = {
            ta_name: therapyArea,
            scenario_name: scenario,
            indication,
            lot,
            product,
            start_date: startDate,
            end_date: endDate,
        };

        console.log("Apply Filter Payload", payload);
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
                                onChange={(e) => {
                                    const value = e.target.value;

                                    setScenario(value);
                                    setIndication("");
                                    setLot("");
                                    setProduct("");
                                }}
                            >
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

                        <FormControl sx={inputStyle}>
                            <Select
                                value={indication}
                                onChange={(e) => {
                                    const value = e.target.value;

                                    setIndication(value);
                                    setLot("");
                                    setProduct("");
                                }}
                            >
                                {indicationOptions.map((item) => (
                                    <MenuItem key={item} value={item}>
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

                        <FormControl sx={inputStyle}>
                            <Select
                                value={lot}
                                onChange={(e) => {
                                    const value = e.target.value;

                                    setLot(value);
                                    setProduct("");
                                }}
                            >
                                {lotOptions.map((item) => (
                                    <MenuItem key={item} value={item}>
                                        {item}
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

                        <FormControl sx={inputStyle}>
                            <Select
                                value={product}
                                onChange={(e) => {
                                    const value = e.target.value;

                                    setProduct(value);
                                }}
                            >
                                {productOptions.map((item) => (
                                    <MenuItem key={item} value={item}>
                                        {item}
                                    </MenuItem>
                                ))}
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
                            >
                                {availableMonths.map((month) => (
                                    <MenuItem key={month} value={month}>
                                        {dayjs(month).format("MMM YYYY")}
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
                            >
                                {availableMonths
                                    .filter(
                                        (month) =>
                                            dayjs(month).isAfter(startDate)
                                    )
                                    .map((month) => (
                                        <MenuItem key={month} value={month}>
                                            {dayjs(month).format("MMM YYYY")}
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

                {/* OUTPUT TABLE / CHART COMPONENT HERE */}
                {/* <OutputTable outputData={outputData} /> */}
            </Paper >
        </Box >
    );
}