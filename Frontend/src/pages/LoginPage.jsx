import React, { useState } from "react";
import {
    Box,
    Paper,
    TextField,
    Typography,
    Button,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { loginApi } from "../services/apiService";

export default function Login() {
    const navigate = useNavigate();

    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const handleLogin = async () => {
        setError("");

        if (!email || !password) {
            setError("Email and Password are required");
            return;
        }

        try {
            setLoading(true);

            const response = await loginApi({
                email,
                password,
            });

            localStorage.setItem(
                "user",
                JSON.stringify({
                    email: response.data.email,
                })
            );

            navigate("/landingpage");
        } catch (err) {
            setError(
                err?.response?.data?.detail ||
                "Invalid credentials"
            );
        } finally {
            setLoading(false);
        }
    };

    return (
        <Box
            sx={{
                height: "100vh",
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                backgroundColor: "#f5f5f5",
            }}
        >
            <Paper
                elevation={3}
                sx={{
                    width: 420,
                    p: 4,
                    borderRadius: 3,
                }}
            >
                <Typography
                    variant="h5"
                    fontWeight={700}
                    mb={3}
                    textAlign="center"
                >
                    Forecasting Platform
                </Typography>

                <TextField
                    fullWidth
                    label="Email"
                    value={email}
                    onChange={(e) =>
                        setEmail(e.target.value)
                    }
                    sx={{ mb: 2 }}
                />

                <TextField
                    fullWidth
                    type="password"
                    label="Password"
                    value={password}
                    onChange={(e) =>
                        setPassword(e.target.value)
                    }
                    sx={{ mb: 2 }}
                />

                {error && (
                    <Typography
                        color="error"
                        fontSize={14}
                        mb={2}
                    >
                        {error}
                    </Typography>
                )}

                <Button
                    fullWidth
                    variant="contained"
                    onClick={handleLogin}
                    disabled={loading}
                    sx={{
                        textTransform: "none",
                        height: 45,
                    }}
                >
                    {loading
                        ? "Signing In..."
                        : "Login"}
                </Button>

                <Typography
                    variant="body2"
                    sx={{
                        mt: 3,
                        color: "#666",
                    }}
                >
                    Test Users:
                </Typography>

                <Typography
                    variant="caption"
                    display="block"
                >
                    admin@math.com / Admin123
                </Typography>

                <Typography
                    variant="caption"
                    display="block"
                >
                    test@math.com / Test123
                </Typography>
            </Paper>
        </Box>
    );
}