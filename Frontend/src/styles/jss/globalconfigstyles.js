// globalconfigstyles.js

const globalConfigStyles = {
    page: {
        p: 3,
    },

    title: {
        fontSize: "24px",
        fontWeight: 700,
        color: "#0A2342",
    },

    subtitle: {
        fontSize: "16px",
        color: "#5B708B",
        mt: 1,
        mb: 3,
    },

    card: {
        p: 3,
        borderRadius: "16px",
        boxShadow: "none",
        border: "1px solid #D8DEE8",
    },

    sectionTitle: {
        fontSize: "18px",
        fontWeight: 700,
        color: "#0A2342",
        mb: 2,
    },

    label: {
        mb: 1,
        fontSize: "16px",
        fontWeight: 600,
        color: "#64748b",
    },

    row: {
        display: "flex",
        gap: 3,
        flexWrap: "wrap",
    },

    field: {
        flex: 1,
        minWidth: "320px",
    },

    input: {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        fontSize: "14px",
        height: "40px",
        "& .MuiOutlinedInput-root": {
            backgroundColor: "#fcfcfd",
            borderRadius: "8px",
            fontSize: "14px",
            height: "40px",
        },
    },

    select: {
        height: "40px",
        borderRadius: "8px",
        fontSize: "14px",
        bgcolor: "#fcfcfd",
    },

    helperText: {
        fontSize: "15px",
        color: "#64748b",
        flex: 1,
    },

    buttonWrap: {
        display: "flex",
        justifyContent: "flex-end",
        mt: 4,
    },

    button: {
        backgroundColor: "#4F46E5",
        px: 2,
        py: 1,
        borderRadius: "10px",
        textTransform: "none",
    },
};

export default globalConfigStyles;