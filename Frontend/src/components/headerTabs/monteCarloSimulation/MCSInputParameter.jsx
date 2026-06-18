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
    onApplyReRun
}) {

    const handleChange =
        (field) => (e) => {
            setInputParameters((prev) => ({
                ...prev,
                [field]: e.target.value,
            }));
        };

    const headerStyle = {
        fontWeight: 700,
        color: "#64748B",
        fontSize: "15px",
    };

    const inputStyle = {
        "& .MuiOutlinedInput-root": {
            height: "42px",
            borderRadius: "8px",
            backgroundColor: "#fff",
        },
    };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="lg"
            fullWidth
            PaperProps={{
                sx: {
                    borderRadius: "16px",
                    overflow: "hidden",
                },
            }}
        >
            {/* HEADER */}

            <DialogTitle
                sx={{
                    px: 4,
                    py: 3,
                    fontSize: "22px",
                    fontWeight: 700,
                    color: "#1E293B",
                    // borderBottom:
                    //     "1px solid #E2E8F0",
                }}
            >
                Model Input Parameters
                (Adjust Probability Distributions)

                <IconButton
                    onClick={onClose}
                    sx={{
                        position: "absolute",
                        right: 16,
                        top: 16,
                        color: "#64748B",
                    }}
                >
                    <CloseIcon />
                </IconButton>
            </DialogTitle>

            <DialogContent
                sx={{
                    px: 4,
                    py: 3,
                }}
            >

                {/* TABLE HEADER */}

                <Box
                    sx={{
                        display: "grid",
                        gridTemplateColumns:
                            "1.2fr 1.4fr 1fr 1fr",
                        alignItems: "center",
                        backgroundColor:
                            "#F8FAFC",
                        borderBottom:
                            "2px solid #E2E8F0",
                        py: 2,
                        px: 2,
                        mb: 1,
                    }}
                >
                    <Typography sx={headerStyle}>
                        VARIABLE
                    </Typography>

                    <Typography sx={headerStyle}>
                        DISTRIBUTION
                    </Typography>

                    <Typography sx={headerStyle}>
                        BASE MEAN
                    </Typography>

                    <Typography sx={headerStyle}>
                        STD DEV / VOLATILITY
                    </Typography>
                </Box>

                {/* DEMAND */}

                <Box
                    sx={{
                        display: "grid",
                        gridTemplateColumns:
                            "1.2fr 1.4fr 1fr 1fr",
                        alignItems: "center",
                        py: 2.5,
                        px: 2,
                        borderBottom:
                            "1px solid #E2E8F0",
                        gap: 2,
                    }}
                >
                    <Typography
                        sx={{
                            fontSize: "16px",
                            fontWeight: 500,
                        }}
                    >
                        Demand (D)
                    </Typography>

                    <Typography
                        sx={{
                            color: "#334155",
                            fontSize: "16px",
                        }}
                    >
                        Normal
                    </Typography>

                    <TextField
                        size="small"
                        value={
                            inputParameters.demand_mean
                        }
                        onChange={handleChange(
                            "demand_mean"
                        )}
                        sx={inputStyle}
                    />

                    <TextField
                        size="small"
                        value={
                            inputParameters.demand_volatility
                        }
                        onChange={handleChange(
                            "demand_volatility"
                        )}
                        sx={inputStyle}
                    />
                </Box>

                {/* COMPLIANCE */}

                <Box
                    sx={{
                        display: "grid",
                        gridTemplateColumns:
                            "1.2fr 1.4fr 1fr 1fr",
                        alignItems: "center",
                        py: 2.5,
                        px: 2,
                        borderBottom:
                            "1px solid #E2E8F0",
                        gap: 2,
                    }}
                >
                    <Typography
                        sx={{
                            fontSize: "16px",
                            fontWeight: 500,
                        }}
                    >
                        Compliance (C)
                    </Typography>

                    <Typography
                        sx={{
                            color: "#334155",
                            fontSize: "16px",
                        }}
                    >
                        Truncated Normal
                    </Typography>

                    <TextField
                        size="small"
                        value={
                            inputParameters.compliance_mean
                        }
                        onChange={handleChange(
                            "compliance_mean"
                        )}
                        sx={inputStyle}
                    />

                    <TextField
                        size="small"
                        value={
                            inputParameters.compliance_volatility
                        }
                        onChange={handleChange(
                            "compliance_volatility"
                        )}
                        sx={inputStyle}
                    />
                </Box>

                {/* PRICING */}

                <Box
                    sx={{
                        display: "grid",
                        gridTemplateColumns:
                            "1.2fr 1.4fr 1fr 1fr",
                        alignItems: "center",
                        py: 2.5,
                        px: 2,
                        borderBottom:
                            "1px solid #E2E8F0",
                        gap: 2,
                    }}
                >
                    <Typography
                        sx={{
                            fontSize: "16px",
                            fontWeight: 500,
                        }}
                    >
                        Pricing / Dosing
                    </Typography>

                    <Typography
                        sx={{
                            color: "#334155",
                            fontSize: "16px",
                        }}
                    >
                        Fixed
                    </Typography>

                    <TextField
                        size="small"
                        value={
                            inputParameters.pricing_mean
                        }
                        onChange={handleChange(
                            "pricing_mean"
                        )}
                        sx={inputStyle}
                    />

                    <TextField
                        size="small"
                        value={
                            inputParameters.pricing_volatility
                        }
                        onChange={handleChange(
                            "pricing_volatility"
                        )}
                        sx={inputStyle}
                    />
                </Box>

                {/* FOOTER NOTE */}

                <Typography
                    sx={{
                        mt: 3,
                        color: "#64748B",
                        fontSize: "14px",
                    }}
                >
                    * Modifying these values updates
                    the stochastic engine calculations.
                    Compliance is truncated between
                    0 and 1.
                </Typography>

                {/* BUTTON */}

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
                        onClick={onApplyReRun}
                        sx={{
                            textTransform:
                                "none",
                            borderRadius:
                                "10px",
                            px: 4,
                            py: 1.2,
                            fontWeight: 700,
                            backgroundColor:
                                "#4F46E5",

                            "&:hover": {
                                backgroundColor:
                                    "#4338CA",
                            },
                        }}
                    >
                        Apply & Re-Run
                    </Button>
                </Box>

            </DialogContent>
        </Dialog>
    );
}