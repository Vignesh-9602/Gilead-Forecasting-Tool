import React from "react";

import {
    Dialog,
    DialogTitle,
    DialogContent,
    Box,
    Typography,
    TextField,
    Button,
    IconButton,
} from "@mui/material";

import CloseIcon from "@mui/icons-material/Close";

export default function MCSInputParametersDialog({
    open,
    onClose,
    inputParameters,
    setInputParameters,
}) {
    const handleChange =
        (field) => (e) => {
            setInputParameters((prev) => ({
                ...prev,
                [field]: e.target.value,
            }));
        };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="lg"
            fullWidth
        >
            <DialogTitle
                sx={{
                    fontWeight: 700,
                    fontSize: "32px",
                }}
            >
                Model Input Parameters
                (Adjust Probability Distributions)

                <IconButton
                    onClick={onClose}
                    sx={{
                        position: "absolute",
                        right: 12,
                        top: 12,
                    }}
                >
                    <CloseIcon />
                </IconButton>
            </DialogTitle>

            <DialogContent>

                {/* Header */}

                <Box
                    sx={{
                        display: "grid",
                        gridTemplateColumns:
                            "1.2fr 1.2fr 1fr 1fr",
                        py: 2,
                        borderBottom:
                            "1px solid #D8DEE8",
                        fontWeight: 700,
                        color: "#64748B",
                    }}
                >
                    <Typography>
                        VARIABLE
                    </Typography>

                    <Typography>
                        DISTRIBUTION
                    </Typography>

                    <Typography>
                        BASE MEAN
                    </Typography>

                    <Typography>
                        STD DEV /
                        VOLATILITY
                    </Typography>
                </Box>

                {/* Demand */}

                <Box
                    sx={{
                        display: "grid",
                        gridTemplateColumns:
                            "1.2fr 1.2fr 1fr 1fr",
                        py: 2,
                        alignItems: "center",
                    }}
                >
                    <Typography>
                        Demand (D)
                    </Typography>

                    <Typography>
                        Normal
                    </Typography>

                    <TextField
                        value={
                            inputParameters.demand_mean
                        }
                        onChange={handleChange(
                            "demand_mean"
                        )}
                        size="small"
                    />

                    <TextField
                        value={
                            inputParameters.demand_volatility
                        }
                        onChange={handleChange(
                            "demand_volatility"
                        )}
                        size="small"
                    />
                </Box>

                {/* Compliance */}

                <Box
                    sx={{
                        display: "grid",
                        gridTemplateColumns:
                            "1.2fr 1.2fr 1fr 1fr",
                        py: 2,
                        alignItems: "center",
                    }}
                >
                    <Typography>
                        Compliance (C)
                    </Typography>

                    <Typography>
                        Truncated Normal
                    </Typography>

                    <TextField
                        value={
                            inputParameters.compliance_mean
                        }
                        onChange={handleChange(
                            "compliance_mean"
                        )}
                        size="small"
                    />

                    <TextField
                        value={
                            inputParameters.compliance_volatility
                        }
                        onChange={handleChange(
                            "compliance_volatility"
                        )}
                        size="small"
                    />
                </Box>

                {/* Pricing */}

                <Box
                    sx={{
                        display: "grid",
                        gridTemplateColumns:
                            "1.2fr 1.2fr 1fr 1fr",
                        py: 2,
                        alignItems: "center",
                    }}
                >
                    <Typography>
                        Pricing / Dosing
                    </Typography>

                    <Typography>
                        Fixed
                    </Typography>

                    <TextField
                        value={
                            inputParameters.pricing_mean
                        }
                        onChange={handleChange(
                            "pricing_mean"
                        )}
                        size="small"
                    />

                    <TextField
                        value={
                            inputParameters.pricing_volatility
                        }
                        onChange={handleChange(
                            "pricing_volatility"
                        )}
                        size="small"
                    />
                </Box>

                <Box
                    sx={{
                        display: "flex",
                        justifyContent:
                            "flex-end",
                        mt: 4,
                    }}
                >
                    <Button
                        variant="contained"
                        sx={{
                            textTransform:
                                "none",
                            borderRadius:
                                "8px",
                        }}
                    >
                        Apply & Re-Run
                    </Button>
                </Box>
            </DialogContent>
        </Dialog>
    );
}