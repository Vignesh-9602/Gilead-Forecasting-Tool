import React, { useContext, useEffect, useState, } from "react";
import { Box, Paper, Typography, FormControl, Select, MenuItem, Button, } from "@mui/material";
import dayjs from "dayjs";
import { GlobalContext } from "../../../context/Provider";
import RevenueChart from "./RevenueChart";
import RevenueTable from "./RevenueTable";
import { getNetRevenueFilters, applyNetRevenueFilter, editNetRevenue } from "../../../services/apiService";
import { useSnackbarStore, useLoadingStore } from "../../../stores";

export default function NetDemandRevenue() {
    const { favState } = useContext(GlobalContext);
    const therapyArea = favState?.selectedTherapyArea;

    const [scenarioName, setScenarioName] = useState("");

    const [product, setProduct] = useState("");

    const [startDate, setStartDate] = useState("");

    const [endDate, setEndDate] = useState("");

    const [scenarioOptions, setScenarioOptions] = useState([]);

    const [productsByScenario, setProductsByScenario] = useState({});

    const [availableMonths, setAvailableMonths] = useState([]);

    const [chartData, setChartData] = useState(null);

    const [tableData, setTableData] = useState(null);

    // const [loading, setLoading] = useState(false);

    const { showSnackbar } = useSnackbarStore();
    const { setLoading, isLoading } = useLoadingStore();

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

    const labelStyle = {
        mb: 1,
        fontSize: "14px",
        fontWeight: 700,
        color: "#64748b",
    };
    useEffect(() => {
        if (therapyArea) {
            fetchFilters();
        }
    }, [therapyArea]);

    useEffect(() => {
        if (!scenarioName) return;

        const scenarioProducts =
            productsByScenario?.[scenarioName] || [];

        if (
            !scenarioProducts.includes(product)
        ) {
            setProduct(
                scenarioProducts[0] || ""
            );
        }
    }, [scenarioName, productsByScenario]);

    const fetchFilters = async () => {
        try {
            setLoading(true);
            const { data } = await getNetRevenueFilters(
                therapyArea
            );

            setScenarioOptions(
                data?.scenario_names || []
            );

            setProductsByScenario(
                data?.products_by_scenario || {}
            );

            setAvailableMonths(
                data?.available_months || []
            );

            const defaultFilter =
                data?.selected_filter;

            if (defaultFilter) {
                setScenarioName(
                    defaultFilter.scenario_name || ""
                );

                setProduct(
                    defaultFilter.product || ""
                );

                setStartDate(
                    defaultFilter.start_date || ""
                );

                setEndDate(
                    defaultFilter.end_date || ""
                );
            }
            const { data: revenueData } =
                await applyNetRevenueFilter({
                    ta_name: therapyArea,
                    scenario_name:
                        defaultFilter.scenario_name,
                    product:
                        defaultFilter.product,
                    start_date:
                        defaultFilter.start_date,
                    end_date:
                        defaultFilter.end_date,
                });

            setChartData(
                revenueData?.chart || null
            );

            setTableData(
                revenueData?.table || null
            );
        } catch (error) {
            console.error(
                "Error fetching Net Revenue filters",
                error
            );
        } finally {
            setLoading(false);
        }
    };

    const productOptions = productsByScenario?.[scenarioName] || [];

    // useEffect(() => {
    //     setProduct("");
    // }, [scenarioName]);

    const isApplyEnabled =
        !!scenarioName &&
        !!product &&
        !!startDate &&
        !!endDate;

    const handleApplyFilter = async () => {
        try {
            setLoading(true);

            const payload = {
                ta_name: therapyArea,
                scenario_name: scenarioName,
                product,
                start_date: startDate,
                end_date: endDate,
            };

            const { data } =
                await applyNetRevenueFilter(payload);

            setChartData(data?.chart || null);

            setTableData(data?.table || null);
            showSnackbar("Filters applied successfully", "success");

        } catch (error) {
            console.error(
                "Error applying Net Revenue filter",
                error
            );
            showSnackbar("Failed to apply demand revenue filter", "error");
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
                                minWidth: "150px",
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
                                value={scenarioName}
                                onChange={(e) =>
                                    setScenarioName(
                                        e.target.value
                                    )
                                }
                                displayEmpty
                            >
                                <MenuItem
                                    value=""
                                    disabled
                                >
                                    Select Scenario
                                </MenuItem>

                                {scenarioOptions.map(
                                    (item) => (
                                        <MenuItem
                                            key={item}
                                            value={item}
                                        >
                                            {item}
                                        </MenuItem>
                                    )
                                )}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* PRODUCT */}

                    <Box>
                        <Typography sx={labelStyle}>
                            PRODUCT
                        </Typography>

                        <FormControl
                            sx={inputStyle}
                            disabled={!scenarioName}
                        >
                            <Select
                                value={product}
                                onChange={(e) =>
                                    setProduct(
                                        e.target.value
                                    )
                                }
                                displayEmpty
                            >
                                <MenuItem
                                    value=""
                                    disabled
                                >
                                    Select Product
                                </MenuItem>

                                {productOptions.map(
                                    (item) => (
                                        <MenuItem
                                            key={item}
                                            value={item}
                                        >
                                            {item}
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
                                onChange={(e) =>
                                    setStartDate(
                                        e.target.value
                                    )
                                }
                                MenuProps={{
                                    PaperProps: {
                                        sx: {
                                            maxHeight: 300,
                                            width: 130,
                                        },
                                    },
                                }}
                            >
                                {availableMonths.map(
                                    (month) => (
                                        <MenuItem
                                            key={month}
                                            value={month}
                                        >
                                            {dayjs(
                                                month
                                            ).format(
                                                "MMM YY"
                                            )}
                                        </MenuItem>
                                    )
                                )}
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
                                onChange={(e) =>
                                    setEndDate(
                                        e.target.value
                                    )
                                }
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
                                        (
                                            month
                                        ) =>
                                            dayjs(
                                                month
                                            ).isAfter(
                                                startDate
                                            )
                                    )
                                    .map(
                                        (
                                            month
                                        ) => (
                                            <MenuItem
                                                key={
                                                    month
                                                }
                                                value={
                                                    month
                                                }
                                            >
                                                {dayjs(
                                                    month
                                                ).format(
                                                    "MMM YY"
                                                )}
                                            </MenuItem>
                                        )
                                    )}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* APPLY FILTER */}

                    <Button
                        variant="contained"
                        onClick={
                            handleApplyFilter
                        }
                        disabled={
                            !isApplyEnabled
                        }
                        sx={{
                            height: "40px",
                            px: 3,
                            borderRadius: "8px",
                            textTransform:
                                "none",
                            backgroundColor:
                                "#4F46E5",
                        }}
                    >
                        Apply Filter
                    </Button>
                </Box>
            </Paper>

            <RevenueChart chartData={chartData} />
            <RevenueTable tableData={tableData}
                forecastStartIndex={
                    chartData?.forecast_start_index ?? 0
                }
                ta_name={therapyArea}
                scenario_name={scenarioName}
                product={product}
                startDate={startDate}
                endDate={endDate}
                onRevenueUpdated={(response) => {
                    setChartData(response.chart);
                    setTableData(response.table);
                }}
            />
        </Box>
    );
}