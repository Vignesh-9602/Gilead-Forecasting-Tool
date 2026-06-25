import React from "react";

import {
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
} from "@mui/material";

const months = [
    "Jan-24",
    "Feb-24",
    "Mar-24",
    "Apr-24",
    "May-24",
    "Jun-24",
    "Jul-24",
    "Aug-24",
    "Sep-24",
    "Oct-24",
    "Nov-24",
    "Dec-24",
];

export default function HIVMarketTable({
    tableData = [],
}) {
    if (!tableData.length) return null;

    return (
        <Paper
            sx={{
                mt: 3,
                borderRadius: "12px",
                border: "1px solid #D8DEE8",
                boxShadow: "none",
            }}
        >
            <TableContainer
                sx={{
                    maxHeight: 500,
                    overflow: "auto",
                }}
            >
                <Table stickyHeader size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell
                                sx={{
                                    minWidth: 180,
                                    fontWeight: 700,
                                    background: "#F8FAFC",
                                    position: "sticky",
                                    left: 0,
                                    zIndex: 10,
                                }}
                            >
                                Category
                            </TableCell>

                            {months.map((month) => (
                                <TableCell
                                    key={month}
                                    align="center"
                                    sx={{
                                        fontWeight: 700,
                                        background: "#F8FAFC",
                                        minWidth: 90,
                                    }}
                                >
                                    {month}
                                </TableCell>
                            ))}
                        </TableRow>
                    </TableHead>

                    <TableBody>
                        {tableData.map((row) => (
                            <TableRow
                                key={row.label}
                                hover
                            >
                                <TableCell
                                    sx={{
                                        position: "sticky",
                                        left: 0,
                                        background: "#fff",
                                        fontWeight: 600,
                                    }}
                                >
                                    {row.label}
                                </TableCell>

                                {row.values.map(
                                    (value, index) => (
                                        <TableCell
                                            key={index}
                                            align="center"
                                        >
                                            {Number(
                                                value
                                            ).toLocaleString()}
                                        </TableCell>
                                    )
                                )}
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Paper>
    );
}