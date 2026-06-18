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
    TextField,
} from "@mui/material";

import { GlobalContext } from "../../../context/Provider";
import MCSChart from "./MCSChart";
import MCSInputParametersDialog from "./MCSInputParameter";
import { getMonteCarloFilters, runMonteCarloSimulation } from "../../../services/apiService";
import { useSnackbarStore, useLoadingStore, } from "../../../stores";

export default function MonteCarloSimulation() {

    const { favState } = useContext(GlobalContext);

    const therapyArea = favState?.selectedTherapyArea;

    const [products, setProducts] = useState("");

    const [simulationIterations, setSimulationIterations] = useState("100");

    const [confidenceInterval, setConfidenceInterval] = useState("");

    const [simulationResult, setSimulationResult] = useState(null);

    const [inputParameterOpen, setInputParameterOpen] =
        useState(false);

    const [inputParameters, setInputParameters] =
        useState({
            demand_mean: 100,
            demand_volatility: 0.15,

            compliance_mean: 0.85,
            compliance_volatility: 0.05,

            pricing_mean: 1.0,
            pricing_volatility: 0.0,
        });

    const [filterOptions, setFilterOptions] =
        useState({
            brands: [],
            confidence_interval_options: [],
        });

    const { showSnackbar } =
        useSnackbarStore();

    const { setLoading } =
        useLoadingStore();

    const brandOptions = filterOptions?.brands || [];

    const confidenceOptions =
        filterOptions?.confidence_interval_options ||
        [];

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

    const formatNumber = (value) =>
        Number(value).toLocaleString(
            "en-US",
            {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            }
        );

    useEffect(() => {
        if (therapyArea) {
            fetchMonteCarloFilters();
        }
    }, [therapyArea]);

    const fetchMonteCarloFilters =
        async () => {
            try {
                setLoading(true);

                const response =
                    await getMonteCarloFilters(
                        therapyArea
                    );

                const resData =
                    response?.data;

                setFilterOptions(
                    resData || {
                        brands: [],
                        confidence_interval_options:
                            [],
                    }
                );

                const defaultFilter =
                    resData?.selected_filter;

                if (defaultFilter) {

                    setProducts(
                        defaultFilter.brand || ""
                    );

                    setConfidenceInterval(
                        defaultFilter.confidence_interval ||
                        ""
                    );

                    setSimulationIterations(
                        String(
                            defaultFilter.n_iterations ||
                            100
                        )
                    );

                    // Auto Run Projection Engine

                    await runSimulation(
                        null,
                        {
                            ta_name:
                                therapyArea,

                            brand:
                                defaultFilter.brand,

                            n_iterations:
                                defaultFilter.n_iterations,

                            confidence_interval:
                                defaultFilter.confidence_interval,
                        }
                    );
                }
            } catch (error) {
                console.error(
                    "Failed to fetch Monte Carlo filters",
                    error
                );

                showSnackbar(
                    "Failed to fetch Monte Carlo filters",
                    "error"
                );
            } finally {
                setLoading(false);
            }
        };

    const runSimulation = async (
        overrideParams = null,
        customFilters = null
    ) => {
        const payload =
            customFilters || {
                ta_name: therapyArea,
                brand: products,
                n_iterations: Number(
                    simulationIterations
                ),
                confidence_interval:
                    confidenceInterval,

                ...(overrideParams || {}),
            };

        try {
            setLoading(true);

            const response =
                await runMonteCarloSimulation(
                    payload
                );

            const result =
                response?.data;

            setSimulationResult(result);

            if (
                result?.input_parameters
            ) {
                setInputParameters({
                    demand_mean: formatNumber(
                        result.input_parameters
                            .demand_base_mean
                    ),

                    demand_volatility:
                        formatNumber(
                            result.input_parameters
                                .demand_volatility
                        ),

                    compliance_mean:
                        formatNumber(
                            result.input_parameters
                                .compliance_mean
                        ),

                    compliance_volatility:
                        formatNumber(
                            result.input_parameters
                                .compliance_volatility
                        ),

                    pricing_mean:
                        formatNumber(
                            result.input_parameters
                                .price_per_vial
                        ),

                    pricing_volatility:
                        formatNumber(
                            result.input_parameters
                                .pricing_std
                        ),
                });
            }
        } catch (error) {
            console.error(error);

            showSnackbar(
                "Failed to run Monte Carlo simulation",
                "error"
            );
        } finally {
            setLoading(false);
        }
    };

    const handleApplyFilter =
        async () => {
            await runSimulation();
        };

    const handleReRun =
        async () => {
            const payload = {
                demand_params: {
                    base_mean: Number(
                        inputParameters.demand_mean
                    ),
                    std_pct: Number(
                        inputParameters.demand_volatility
                    ),
                },

                compliance_params: {
                    mean: Number(
                        inputParameters.compliance_mean
                    ),
                    std: Number(
                        inputParameters.compliance_volatility
                    ),
                },

                pricing_params: {
                    price_per_vial: Number(
                        inputParameters.pricing_mean
                    ),
                    std: Number(
                        inputParameters.pricing_volatility
                    ),
                },
            };

            await runSimulation(
                payload
            );

            setInputParameterOpen(
                false
            );
        };

    const isApplyEnabled =
        !!therapyArea &&
        !!products &&
        !!simulationIterations &&
        !!confidenceInterval;

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
                        justifyContent: "space-between",
                        alignItems: "flex-end",
                        gap: 2,
                        width: "100%",
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

                        {/* PRODUCT MULTI SELECT */}
                        <Box>
                            <Typography sx={labelStyle}>
                                PRODUCT
                            </Typography>

                            <FormControl sx={{ ...inputStyle, maxWidth: 220 }}>
                                <Select
                                    value={products}
                                    onChange={(e) => setProducts(e.target.value)}
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

                        {/* SIMULATION ITERATIONS */}
                        <Box>
                            <Typography sx={labelStyle}>
                                SIMULATION ITERATIONS
                            </Typography>

                            <TextField
                                type="number"
                                value={
                                    simulationIterations
                                }
                                onChange={(e) =>
                                    setSimulationIterations(
                                        e.target.value
                                    )
                                }
                                placeholder="Enter Iterations"
                                sx={{
                                    maxWidth: "140px",

                                    "& .MuiOutlinedInput-root":
                                    {
                                        height: "35px",
                                        borderRadius:
                                            "8px",
                                        backgroundColor:
                                            "#fcfcfd",
                                    },
                                }}
                            />
                        </Box>

                        {/* CONFIDENCE INTERVAL */}
                        <Box>
                            <Typography sx={labelStyle}>
                                CONFIDENCE INTERVAL
                            </Typography>

                            <FormControl sx={inputStyle}>
                                <Select
                                    value={
                                        confidenceInterval
                                    }
                                    onChange={(e) =>
                                        setConfidenceInterval(
                                            e.target.value
                                        )
                                    }
                                    displayEmpty
                                >
                                    <MenuItem
                                        value=""
                                        disabled
                                    >
                                        Select Interval
                                    </MenuItem>

                                    {confidenceOptions.map((item) => (
                                        <MenuItem
                                            key={item.value}
                                            value={item.value}
                                        >
                                            {item.label}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Box>

                        {/* APPLY FILTER */}
                        <Button
                            variant="contained"
                            onClick={
                                handleApplyFilter
                            }
                            // disabled={!isApplyEnabled}
                            sx={{
                                height: "40px",
                                px: 3,
                                borderRadius: "8px",
                                textTransform: "none",
                                backgroundColor:
                                    "#4F46E5",
                            }}
                        >
                            Run Projection Engine
                        </Button>
                    </Box>
                    <Box>
                        <Button
                            variant="outlined"
                            onClick={() =>
                                setInputParameterOpen(true)
                            }
                            sx={{
                                height: "40px",
                                px: 2,
                                borderRadius: "8px",
                                textTransform: "none",
                                borderColor: "#aaa8a89e",
                                color: "#000",
                                fontWeight: 500,
                                whiteSpace: "nowrap",

                                // "&:hover": {
                                //     borderColor: "#4338CA",
                                // },
                            }}
                        >
                            View Input Parameters
                        </Button>
                    </Box>
                </Box>
            </Paper>
            {/* {simulationResult && (
                <MCSChart
                    data={simulationResult}
                />
            )} */}
            {/* {simulationResult && ( */}
            <MCSChart data={simulationResult} />
            {/* )} */}

            <MCSInputParametersDialog
                open={inputParameterOpen}
                onClose={() =>
                    setInputParameterOpen(false)
                }
                inputParameters={inputParameters}
                setInputParameters={setInputParameters}
                onApplyReRun={
                    handleReRun
                }
            />
        </Box>
    );
}