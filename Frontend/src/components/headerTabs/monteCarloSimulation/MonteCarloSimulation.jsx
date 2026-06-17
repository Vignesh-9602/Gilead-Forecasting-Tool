import React, { useContext, useState } from "react";

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

export default function MonteCarloSimulation() {

    const { favState } = useContext(GlobalContext);

    const therapyArea = favState?.selectedTherapyArea;

    const [products, setProducts] = useState([]);

    const [simulationIterations, setSimulationIterations] = useState("100");

    const [confidenceInterval, setConfidenceInterval] = useState("");

    const [simulationResult, setSimulationResult] = useState({
        histogram: [
            {
                range: "112.6M-115.7M",
                count: 4,
            },
            {
                range: "115.7M-118.8M",
                count: 12,
            },
            {
                range: "118.8M-121.9M",
                count: 27,
            },
            {
                range: "121.9M-125.0M",
                count: 58,
            },
            {
                range: "125.0M-128.1M",
                count: 96,
            },
            {
                range: "128.1M-131.2M",
                count: 142,
            },
            {
                range: "131.2M-134.3M",
                count: 186,
            },
            {
                range: "134.3M-137.4M",
                count: 173,
            },
            {
                range: "137.4M-140.5M",
                count: 121,
            },
            {
                range: "140.5M-143.6M",
                count: 72,
            },
            {
                range: "143.6M-146.7M",
                count: 44,
            },
            {
                range: "146.7M-149.8M",
                count: 23,
            },
            {
                range: "149.8M-152.9M",
                count: 8,
            },
        ],

        summary: {
            number_of_simulations: 1000,
            mean_revenue: 134571999,
            median_revenue: 134717174,
            std_dev_revenue: 7454883,
            min_revenue: 112563720,
            max_revenue: 159422903,
            percentile_5: 122406758,
            percentile_25: 129354026,
            percentile_75: 139681491,
            percentile_95: 146894460,
        },

        input_parameters: {
            demand_volatility: 0.15,
            compliance_mean: 0.85,
            compliance_volatility: 0.05,
        },
    });

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

    // Replace with API response
    const filterOptions = {
        brands: [
            "Taxanes",
            "Taxanes+",
            "TPC",
            "TPC+",
            "Trodelvy",
            "Trodelvy Combo",
        ],

        confidence_intervals: [
            "Standard (90%)",
            "High (95%)",
            "Very High (99%)",
        ],
    };

    // const [filterOptions, setFilterOptions] = useState({
    //     brands: [],
    //     confidence_intervals: [],
    // });

    // useEffect(() => {
    //     fetchMonteCarloFilters();
    // }, [therapyArea]);

    // const fetchMonteCarloFilters = async () => {
    //     try {
    //         const response =
    //             await getMonteCarloFilters(
    //                 therapyArea
    //             );

    //         setFilterOptions(
    //             response?.data || {}
    //         );
    //     } catch (error) {
    //         console.error(error);
    //     }
    // };

    const brandOptions = filterOptions?.brands || [];

    const confidenceOptions =
        filterOptions?.confidence_intervals || [];

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
        const payload = {
            ta_name: therapyArea,
            brands: products,
            simulation_iterations: Number(simulationIterations),
            confidence_interval: confidenceInterval,
        };

        try {
            // const response = await runMonteCarloSimulation(payload);

            // mock response for now
            const response = {
                data: {
                    histogram: [
                        {
                            range: "112.6M-115.7M",
                            count: 4,
                        },
                        {
                            range: "115.7M-118.8M",
                            count: 12,
                        },
                        {
                            range: "118.8M-121.9M",
                            count: 27,
                        },
                    ],
                    summary: {
                        number_of_simulations: 1000,
                        mean_revenue: 134571999,
                        median_revenue: 134717174,
                        std_dev_revenue: 7454883,
                        min_revenue: 112563720,
                        max_revenue: 159422903,
                        percentile_5: 122406758,
                        percentile_25: 129354026,
                        percentile_75: 139681491,
                        percentile_95: 146894460,
                    },
                    input_parameters: {
                        demand_volatility: 0.15,
                        compliance_mean: 0.85,
                        compliance_volatility: 0.05,
                    },
                },
            };

            setSimulationResult(response.data);
        } catch (error) {
            console.error(error);
        }
    };

    const isApplyEnabled =
        !!therapyArea &&
        products.length > 0 &&
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
                                    multiple
                                    value={products}
                                    onChange={(e) => {

                                        const value =
                                            e.target.value;

                                        if (
                                            value.includes(
                                                "SELECT_ALL"
                                            )
                                        ) {
                                            if (
                                                products.length ===
                                                brandOptions.length
                                            ) {
                                                setProducts([]);
                                            } else {
                                                setProducts(
                                                    brandOptions
                                                );
                                            }
                                        } else {
                                            setProducts(value);
                                        }
                                    }}
                                    displayEmpty
                                    renderValue={(selected) =>
                                        selected.length === 0
                                            ? "Select Products"
                                            : selected.join(
                                                ", "
                                            )
                                    }
                                >
                                    <MenuItem value="SELECT_ALL">
                                        <Checkbox
                                            checked={
                                                products.length ===
                                                brandOptions.length &&
                                                brandOptions.length >
                                                0
                                            }
                                            indeterminate={
                                                products.length >
                                                0 &&
                                                products.length <
                                                brandOptions.length
                                            }
                                        />

                                        <ListItemText
                                            primary="Select All"
                                        />
                                    </MenuItem>

                                    {brandOptions.map(
                                        (item) => (
                                            <MenuItem
                                                key={item}
                                                value={item}
                                            >
                                                <Checkbox
                                                    checked={products.includes(
                                                        item
                                                    )}
                                                />

                                                <ListItemText
                                                    primary={
                                                        item
                                                    }
                                                />
                                            </MenuItem>
                                        )
                                    )}
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

                                    {confidenceOptions.map(
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

                        {/* APPLY FILTER */}
                        <Button
                            variant="contained"
                            // onClick={
                            //     handleApplyFilter
                            // }
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
            <MCSChart data={simulationResult} />
            <MCSInputParametersDialog
                open={inputParameterOpen}
                onClose={() =>
                    setInputParameterOpen(false)
                }
                inputParameters={inputParameters}
                setInputParameters={setInputParameters}
            />
        </Box>
    );
}