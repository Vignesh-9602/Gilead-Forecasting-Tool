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

export default function MonteCarloSimulation() {

    const { favState } = useContext(GlobalContext);

    const therapyArea = favState?.selectedTherapyArea;

    const [products, setProducts] = useState([]);

    const [simulationIterations, setSimulationIterations] = useState("100");

    const [confidenceInterval, setConfidenceInterval] = useState("");

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
            simulation_iterations: Number(
                simulationIterations
            ),
            confidence_interval: confidenceInterval,
        };

        console.log("Monte Carlo Payload", payload);

        // API Call Here
        // await applyMonteCarloFilters(payload);
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
                                    Select Confidence
                                    Interval
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
                        Apply Filter
                    </Button>

                </Box>

            </Paper>

        </Box>
    );
}