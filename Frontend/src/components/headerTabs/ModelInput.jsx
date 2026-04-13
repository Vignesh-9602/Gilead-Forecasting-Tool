import React, { useState, useContext } from "react";
import {
    Box,
    Paper,
    Typography,
    FormControl,
    Select,
    MenuItem,
    TextField,
    Button,
} from "@mui/material";
import Slider from "@mui/material/Slider";
import { GlobalContext } from "../../context/Provider";

export default function ModelInput() {
    const [indication, setIndication] = useState("");
    const [lot, setLot] = useState("");
    const [metric, setMetric] = useState("");
    const [brand, setBrand] = useState("");
    const [scenarioName, setScenarioName] = useState("");
    const [editable, setEditable] = useState(false);

    const [multiplier, setMultiplier] = useState(1.0);
    const [alpha, setAlpha] = useState(0.3);
    const [beta, setBeta] = useState(0.1);
    const [gamma, setGamma] = useState(0.9);

    const [trendType, setTrendType] = useState("");
    const [seasonality, setSeasonality] = useState("None");
    const { favState } = useContext(GlobalContext);
    const therapyArea = favState?.selectedTherapyArea;

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
                        justifyContent: "space-between",
                        alignItems: "end",
                        gap: 3,
                        flexWrap: "wrap",
                    }}
                >
                    {/* LEFT SIDE */}
                    <Box
                        sx={{
                            display: "flex",
                            gap: 3,
                            flexWrap: "wrap",
                            alignItems: "end",
                        }}
                    >
                        {/* Therapeutic Area */}
                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
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
                                <Typography>{therapyArea}</Typography>
                            </Box>
                        </Box>

                        {/* Indication */}
                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                                INDICATION
                            </Typography>

                            <FormControl sx={inputStyle}>
                                <Select value={indication} onChange={(e) => setIndication(e.target.value)} displayEmpty>
                                    <MenuItem value="" disabled>
                                        Select Indication
                                    </MenuItem>
                                    <MenuItem value="TNBC">TNBC</MenuItem>
                                    <MenuItem value="HR+">HR+</MenuItem>
                                    <MenuItem value="Indication 3">Indication 3</MenuItem>
                                    <MenuItem value="Indication 4">Indication 4</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>

                        {/* LOT */}
                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                                LOT
                            </Typography>

                            <FormControl sx={inputStyle}>
                                <Select value={lot} onChange={(e) => setLot(e.target.value)} displayEmpty>
                                    <MenuItem value="" disabled>
                                        Select LOT
                                    </MenuItem>
                                    <MenuItem value="1L">1L</MenuItem>
                                    <MenuItem value="2L">2L</MenuItem>
                                    <MenuItem value="3L">3L</MenuItem>
                                    <MenuItem value="4L">4L</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>

                        {/* Metric */}
                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                                METRIC
                            </Typography>

                            <FormControl sx={inputStyle}>
                                <Select
                                    value={metric}
                                    onChange={(e) => {
                                        setMetric(e.target.value);
                                        if (e.target.value === "New Patient Starts") {
                                            setBrand("");
                                        }
                                    }}
                                    displayEmpty
                                >
                                    <MenuItem value="" disabled>
                                        Select Metric
                                    </MenuItem>
                                    <MenuItem value="Market Share">Market Share</MenuItem>
                                    <MenuItem value="New Patient Starts">New Patient Starts</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>

                        {/* Brand */}
                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                                PRODUCT
                            </Typography>

                            <FormControl sx={inputStyle}>
                                <Select
                                    value={brand}
                                    onChange={(e) => setBrand(e.target.value)}
                                    disabled={metric === "New Patient Starts"}
                                    displayEmpty
                                >
                                    <MenuItem value="" disabled>
                                        Select Product
                                    </MenuItem>
                                    <MenuItem value="Trodelvy">Trodelvy</MenuItem>
                                    <MenuItem value="Combo">Combo</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>
                    </Box>

                    {/* RIGHT SIDE */}
                    <Box
                        sx={{
                            display: "flex",
                            gap: 2,
                            alignItems: "end",
                        }}
                    >
                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>
                                SCENARIO NAME
                            </Typography>

                            <TextField
                                placeholder="e.g. Adjusted Baseline"
                                value={scenarioName}
                                onChange={(e) => setScenarioName(e.target.value)}
                                sx={{
                                    ...inputStyle,
                                    minWidth: "220px",
                                }}
                            />
                        </Box>

                        <Button
                            variant="contained"
                            sx={{
                                height: "35px",
                                px: 4,
                                borderRadius: "10px",
                                backgroundColor: "#4F46E5",
                                textTransform: "none",
                            }}
                        >
                            Save Scenario
                        </Button>
                    </Box>
                </Box>

                {/* slider */}
                <Paper
                    sx={{
                        mt: 3,
                        p: 3,
                        borderRadius: "16px",
                        border: "1px solid #D8DEE8",
                        boxShadow: "none",
                        backgroundColor: editable ? "#fff" : "#eff6ff",
                    }}
                >
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                        <Typography
                            sx={{
                                fontSize: "14px",
                                fontWeight: 700,
                                color: "#1d4ed8",
                                textTransform: "uppercase",
                            }}
                        >
                            Trend Adjustment Factor
                        </Typography>

                        <Button
                            variant="outlined"
                            size="small"
                            onClick={() => setEditable(!editable)}
                            sx={{
                                textTransform: "none",
                                borderRadius: "8px",
                            }}
                        >
                            {editable ? "Lock Factors" : "Edit Factors"}
                        </Button>
                    </Box>

                    <Box
                        sx={{
                            display: "flex",
                            gap: 4,
                            flexWrap: "wrap",
                            alignItems: "center",
                        }}
                    >
                        {/* Slider reusable block */}
                        {[
                            {
                                label: "MULTIPLIER",
                                value: multiplier,
                                setValue: setMultiplier,
                                min: 0,
                                max: 3,
                                color: "#d4a373",
                            },
                            {
                                label: "LEVEL (α)",
                                value: alpha,
                                setValue: setAlpha,
                                min: 0,
                                max: 1,
                            },
                            {
                                label: "TREND (β)",
                                value: beta,
                                setValue: setBeta,
                                min: 0,
                                max: 1,
                            },
                            {
                                label: "DAMPING (φ)",
                                value: gamma,
                                setValue: setGamma,
                                min: 0,
                                max: 1,
                            },
                        ].map((item, index) => (
                            <Box key={index} sx={{ width: 160 }}>
                                <Typography
                                    sx={{
                                        fontSize: "14px",
                                        color: editable ? "#64748b" : "#94a3b8",
                                        mb: 1,
                                    }}
                                >
                                    {item.label}{" "}
                                    <span style={{ fontWeight: 700 }}>
                                        {item.value.toFixed(2)}
                                    </span>
                                </Typography>

                                <Slider
                                    value={item.value}
                                    min={item.min}
                                    max={item.max}
                                    step={0.01}
                                    disabled={!editable}
                                    onChange={(e, val) => item.setValue(val)}
                                />
                            </Box>
                        ))}

                        {/* Trend Type */}
                        <Box>
                            <Typography sx={{ fontSize: "13px", fontWeight: 700, color: "#9ca3af", mb: 1 }}>
                                TREND TYPE
                            </Typography>

                            <FormControl sx={inputStyle}>
                                <Select
                                    value={trendType}
                                    onChange={(e) => setTrendType(e.target.value)}
                                    disabled={!editable}
                                    size="small"
                                    displayEmpty
                                >
                                    <MenuItem value="" disabled>
                                        Select Trend Type
                                    </MenuItem>
                                    <MenuItem value="Additive">Additive</MenuItem>
                                    <MenuItem value="Multiplicative">Multiplicative</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>

                        {/* Seasonality */}
                        <Box>
                            <Typography sx={{ fontSize: "13px", fontWeight: 700, color: "#9ca3af", mb: 1 }}>
                                SEASONALITY
                            </Typography>

                            <FormControl sx={inputStyle}>
                                <Select
                                    value={seasonality}
                                    onChange={(e) => setSeasonality(e.target.value)}
                                    disabled={!editable}
                                    size="small"
                                >
                                    <MenuItem value="None">None</MenuItem>
                                    <MenuItem value="Monthly">Monthly</MenuItem>
                                    <MenuItem value="Quarterly">Quarterly</MenuItem>
                                </Select>
                            </FormControl>
                        </Box>

                        {/* Recalculate */}
                        <Button
                            variant="contained"
                            disabled={!editable}
                            sx={{
                                height: "35px",
                                mt: 3,
                                textTransform: "none",
                                backgroundColor: "#6b7280",
                                borderRadius: '8px'
                            }}
                        >
                            Recalculate
                        </Button>
                    </Box>
                </Paper>
            </Paper>
        </Box>
    );
}