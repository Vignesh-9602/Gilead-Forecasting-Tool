export const marketEventMock = {
    ta_name: "HIV Treatment",

    available_scenarios: [
        "BASE",
        "Test Scenario",
        "Scenario 2",
    ],

    available_months: [
        "2024-06-01",
        "2024-07-01",
        "2024-08-01",
        "2024-09-01",
        "2024-10-01",
        "2024-11-01",
        "2024-12-01",
        "2025-01-01",
        "2025-02-01",
        "2025-03-01",
        "2025-04-01",
        "2025-05-01",
    ],

    selected_filter: {
        scenario_name: "BASE",

        markets: [
            "Retail",
        ],

        products: [
            "Truvada",
        ],

        start_date: "2024-06-01",

        end_date: "2025-05-01",
    },

    event_tabs: {

        market_event: {

            impact_curve_configuration: {

                products: [
                    "Biktarvy",
                    "Descovy",
                    "Truvada",
                ],

                markets: [
                    "Retail",
                    "Non-retail",
                ],

                impacted_markets: [
                    "Retail",
                    "Non-retail",
                ],

                curve_types: [
                    "Linear",
                    "Exponential",
                    "Logarithmic",
                    "SCurve",
                ],

                forecast_start_date: "2025-01-01",

                rows: [],
            },

        },

        product_event: {

            impact_curve_configuration: {

                products: [
                    "Biktarvy",
                    "Descovy",
                    "Truvada",
                ],

                markets: [
                    "Retail",
                    "Non-retail",
                ],

                impacted_products: [
                    "Biktarvy",
                    "Descovy",
                    "Truvada",
                ],

                curve_types: [
                    "Linear",
                    "Exponential",
                    "SCurve",
                ],

                forecast_start_date: "2025-01-01",

                rows: [],
            },

        },

        overall_event: {

            impact_curve_configuration: {

                curve_types: [
                    "Linear",
                    "Exponential",
                    "SCurve",
                ],

                forecast_start_date: "2025-01-01",

                rows: [],
            },

        },

    },

};