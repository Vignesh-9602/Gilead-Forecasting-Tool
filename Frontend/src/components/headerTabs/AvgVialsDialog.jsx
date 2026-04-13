import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  Box,
  Typography,
  Button,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  CircularProgress,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { getAverageVials, saveAverageVials } from "../../services/apiService";
import { useSnackbarStore } from "../../stores";

export default function AverageVialsModal({ open, onClose, therapyArea }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const { showSnackbar } = useSnackbarStore();

  useEffect(() => {
    if (open && therapyArea) {
      fetchAverageVials();
    }
  }, [open, therapyArea]);

  const fetchAverageVials = async () => {
    if (!therapyArea) return;

    setLoading(true);

    try {
      const response = await getAverageVials(therapyArea);

      const formattedRows = response?.data?.map((item) => ({
        brand: item.brand,
        dosesPerMonth: item.dose_per_month?.toString() || "",
        averageVials: item.vials_per_month?.toString() || "",
      }));

      setRows(formattedRows);
    } catch (error) {
      console.error("Failed to fetch average vials", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCellChange = (index, field, value) => {
    const updated = [...rows];
    updated[index][field] = value;
    setRows(updated);
  };

  const handleSave = async () => {
    const payload = {
      ta_name: therapyArea,
      avg_vials: rows.map((row) => ({
        brand: row.brand,
        dose_per_month: Number(row.dosesPerMonth),
        vials_per_month: Number(row.averageVials),
      })),
    };

    try {
      await saveAverageVials(payload);

      console.log("Payload:", payload);

      onClose();
      showSnackbar("Configurations saved successfully", "success");

    } catch (error) {
      console.error("Failed to save average vials", error);
      showSnackbar("Failed to dose configuration", "error");
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogContent sx={{ p: 4, borderRadius: "20px" }}>
        <Box display="flex" justifyContent="space-between" mb={3}>
          <Typography fontSize="24px" fontWeight={700}>
            Dose Configuration
          </Typography>

          <IconButton onClick={onClose}>
            <CloseIcon />
          </IconButton>
        </Box>

        {loading ? (
          <Box
            sx={{
              minHeight: "220px",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
            }}
          >
            <CircularProgress />
          </Box>
        ) : (
          <TableContainer
            component={Paper}
            sx={{
              boxShadow: "none",
              border: "1px solid #D8DEE8",
              borderRadius: "12px",
            }}
          >
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Brand</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Doses per Month</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Average Vials</TableCell>
                </TableRow>
              </TableHead>

              <TableBody>
                {rows.map((row, index) => (
                  <TableRow key={index}>
                    <TableCell>{row.brand}</TableCell>

                    <TableCell>
                      <TextField
                        variant="standard"
                        value={row.dosesPerMonth}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (/^\d*$/.test(value)) {
                            handleCellChange(index, "dosesPerMonth", value);
                          }
                        }}
                        fullWidth
                      />
                    </TableCell>

                    <TableCell>
                      <TextField
                        variant="standard"
                        value={row.averageVials}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (/^\d*$/.test(value)) {
                            handleCellChange(index, "averageVials", value);
                          }
                        }}
                        fullWidth
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {!loading && (
          <Box display="flex" justifyContent="flex-end" mt={3}>
            <Button
              variant="contained"
              onClick={handleSave}
              sx={{
                backgroundColor: "#4F46E5",
                px: 4,
                borderRadius: "10px",
                textTransform: "none",
              }}
            >
              Update
            </Button>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}