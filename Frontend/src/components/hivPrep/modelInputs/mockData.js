export const mockData = {
    total_market_volume: {
        chart: {
            months: [
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
            ],

            forecast_start_index: 8,

            series: [
                {
                    label: "Market Volume",

                    history: [
                        32000,
                        33500,
                        34800,
                        36000,
                        38200,
                        39500,
                        41000,
                        42500,
                    ],

                    forecast: [
                        43800,
                        45200,
                        47000,
                        48800,
                    ],
                },
            ],
        },

        table: {
            type: "flat",

            rows: [

                {
                    label: "Market Volume",

                    values: [
                        32000,
                        33500,
                        34800,
                        36000,
                        38200,
                        39500,
                        41000,
                        42500,
                        43800,
                        45200,
                        47000,
                        48800,
                    ],
                },
            ],
        },
    },

    market_distribution: {
        chart: {
            months: [
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
            ],

            forecast_start_index: 8,

            series: [
                {
                    label: "Retail",

                    history: [
                        22000,
                        22800,
                        23600,
                        24500,
                        25500,
                        26200,
                        27000,
                        27800,
                    ],

                    forecast: [
                        28600,
                        29400,
                        30200,
                        31000,
                    ],
                },

                {
                    label: "Non Retail",

                    history: [
                        10000,
                        10700,
                        11200,
                        11500,
                        12700,
                        13300,
                        14000,
                        14700,
                    ],

                    forecast: [
                        15200,
                        15800,
                        16800,
                        17800,
                    ],
                },
            ],
        },

        table: {

            type: "flat",
            rows: [
                {
                    label: "Overall",

                    values: [
                        32000,
                        33500,
                        34800,
                        36000,
                        38200,
                        39500,
                        41000,
                        42500,
                        43800,
                        45200,
                        47000,
                        48800,
                    ],
                },

                {
                    label: "Retail",

                    values: [
                        22000,
                        22800,
                        23600,
                        24500,
                        25500,
                        26200,
                        27000,
                        27800,
                        28600,
                        29400,
                        30200,
                        31000,
                    ],
                },

                {
                    label: "Non Retail",

                    values: [
                        10000,
                        10700,
                        11200,
                        11500,
                        12700,
                        13300,
                        14000,
                        14700,
                        15200,
                        15800,
                        16800,
                        17800,
                    ],
                },
            ],
        },
    },

    product_distribution: {
        chart: {
            months: [
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
            ],

            forecast_start_index: 8,

            series: [
                {
                    label: "Truvada",

                    history: [
                        38,
                        39,
                        38,
                        37,
                        37,
                        36,
                        35,
                        34,
                    ],

                    forecast: [
                        34,
                        33,
                        33,
                        32,
                    ],
                },

                {
                    label: "Descovy",

                    history: [
                        28,
                        29,
                        30,
                        30,
                        31,
                        31,
                        32,
                        33,
                    ],

                    forecast: [
                        34,
                        34,
                        35,
                        35,
                    ],
                },

                {
                    label: "Biktarvy",

                    history: [
                        34,
                        32,
                        32,
                        33,
                        32,
                        33,
                        33,
                        33,
                    ],

                    forecast: [
                        32,
                        33,
                        32,
                        33,
                    ],
                },
            ],
        },

        table: {
            type: "flat",
            rows: [

                {
                    label: "Overall",
                    values: [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
                },

                {
                    label: "Truvada",
                    values: [38, 39, 38, 37, 37, 36, 35, 34, 34, 33, 33, 32],
                },

                {
                    label: "Descovy",
                    values: [28, 29, 30, 30, 31, 31, 32, 33, 34, 34, 35, 35],
                },

                {
                    label: "Biktarvy",
                    values: [34, 32, 32, 33, 32, 33, 33, 33, 32, 33, 32, 33],
                },
            ],
        },
    },

    market_product: {
        chart: {
            months: [
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
            ],

            forecast_start_index: 8,

            series: [
                {
                    label: "Retail - Truvada",
                    history: [9000, 9300, 9500, 9800, 10100, 10400, 10700, 11000],
                    forecast: [11200, 11400, 11600, 11800],
                },
                {
                    label: "Retail - Descovy",
                    history: [6000, 6200, 6400, 6600, 6800, 7000, 7200, 7400],
                    forecast: [7600, 7800, 8000, 8200],
                },
                {
                    label: "Retail - Biktarvy",
                    history: [7000, 7300, 7600, 8100, 8600, 8800, 9100, 9400],
                    forecast: [9800, 10000, 10400, 10800],
                },
                // {
                //     label: "Non Retail - Truvada",
                //     history: [3200, 3300, 3400, 3500, 3600, 3700, 3800, 3900],
                //     forecast: [4000, 4100, 4200, 4300],
                // },
                // {
                //     label: "Non Retail - Descovy",
                //     history: [2900, 3000, 3100, 3200, 3300, 3400, 3500, 3600],
                //     forecast: [3700, 3800, 3900, 4000],
                // },
                // {
                //     label: "Non Retail - Biktarvy",
                //     history: [3900, 4100, 4300, 4450, 4800, 5100, 5400, 5700],
                //     forecast: [5800, 6200, 6500, 6800],
                // },
            ],
        },

        table:
        {
            type: "hierarchy",
            rows: [
                {
                    label: "Retail",

                    values: [
                        22000,
                        22800,
                        23500,
                        24500,
                        25500,
                        26200,
                        27000,
                        27800,
                        28600,
                        29200,
                        30000,
                        30800,
                    ],


                    children: [
                        {
                            label: "Truvada",
                            values: [9000, 9300, 9500, 9800, 10100, 10400, 10700, 11000, 11200, 11400, 11600, 11800],
                        },
                        {
                            label: "Descovy",
                            values: [6000, 6200, 6400, 6600, 6800, 7000, 7200, 7400, 7600, 7800, 8000, 8200],
                        },
                        {
                            label: "Biktarvy",
                            values: [7000, 7300, 7600, 8100, 8600, 8800, 9100, 9400, 9800, 10000, 10400, 10800],
                        },
                    ],
                },

                {
                    label: "Non Retail",

                    values: [
                        10000,
                        10400,
                        10800,
                        11150,
                        11700,
                        12200,
                        12700,
                        13200,
                        13500,
                        14100,
                        14600,
                        15100,
                    ],

                    children: [
                        {
                            label: "Truvada",
                            values: [3200, 3300, 3400, 3500, 3600, 3700, 3800, 3900, 4000, 4100, 4200, 4300],
                        },
                        {
                            label: "Descovy",
                            values: [2900, 3000, 3100, 3200, 3300, 3400, 3500, 3600, 3700, 3800, 3900, 4000],
                        },
                        {
                            label: "Biktarvy",
                            values: [3900, 4100, 4300, 4450, 4800, 5100, 5400, 5700, 5800, 6200, 6500, 6800],
                        },
                    ],
                },
            ],
        },
    },

    product_market: {
        chart: {
            months: [
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
            ],

            forecast_start_index: 8,

            series: [
                {
                    label: "Truvada - Retail",
                    history: [9000, 9300, 9500, 9800, 10100, 10400, 10700, 11000],
                    forecast: [11200, 11400, 11600, 11800],
                },
                {
                    label: "Truvada - Non Retail",
                    history: [3200, 3300, 3400, 3500, 3600, 3700, 3800, 3900],
                    forecast: [4000, 4100, 4200, 4300],
                },
                // {
                //     label: "Descovy - Retail",
                //     history: [6000, 6200, 6400, 6600, 6800, 7000, 7200, 7400],
                //     forecast: [7600, 7800, 8000, 8200],
                // },
                // {
                //     label: "Descovy - Non Retail",
                //     history: [2900, 3000, 3100, 3200, 3300, 3400, 3500, 3600],
                //     forecast: [3700, 3800, 3900, 4000],
                // },
                // {
                //     label: "Biktarvy - Retail",
                //     history: [7000, 7300, 7600, 8100, 8600, 8800, 9100, 9400],
                //     forecast: [9800, 10000, 10400, 10800],
                // },
                // {
                //     label: "Biktarvy - Non Retail",
                //     history: [3900, 4100, 4300, 4450, 4800, 5100, 5400, 5700],
                //     forecast: [5800, 6200, 6500, 6800],
                // },
            ],
        },

        table: {

            type: "hierarchy",

            rows:
                [
                    {
                        label: "Truvada",

                        values: [
                            12200,
                            12600,
                            12900,
                            13300,
                            13700,
                            14100,
                            14500,
                            14900,
                            15200,
                            15500,
                            15800,
                            16100,
                        ],

                        children: [
                            {
                                label: "Retail",
                                values: [9000, 9300, 9500, 9800, 10100, 10400, 10700, 11000, 11200, 11400, 11600, 11800],
                            },
                            {
                                label: "Non Retail",
                                values: [3200, 3300, 3400, 3500, 3600, 3700, 3800, 3900, 4000, 4100, 4200, 4300],
                            },
                        ],
                    },

                    {
                        label: "Descovy",

                        values: [
                            8900,
                            9200,
                            9500,
                            9800,
                            10100,
                            10400,
                            10700,
                            11000,
                            11300,
                            11600,
                            11900,
                            12200,
                        ],

                        children: [
                            {
                                label: "Retail",
                                values: [6000, 6200, 6400, 6600, 6800, 7000, 7200, 7400, 7600, 7800, 8000, 8200],
                            },
                            {
                                label: "Non Retail",
                                values: [2900, 3000, 3100, 3200, 3300, 3400, 3500, 3600, 3700, 3800, 3900, 4000],
                            },
                        ],
                    },

                    {
                        label: "Biktarvy",

                        values: [
                            10900,
                            11400,
                            11900,
                            12550,
                            13400,
                            13900,
                            14500,
                            15100,
                            15600,
                            16200,
                            16900,
                            17600,
                        ],

                        children: [
                            {
                                label: "Retail",
                                values: [7000, 7300, 7600, 8100, 8600, 8800, 9100, 9400, 9800, 10000, 10400, 10800],
                            },
                            {
                                label: "Non Retail",
                                values: [3900, 4100, 4300, 4450, 4800, 5100, 5400, 5700, 5800, 6200, 6500, 6800],
                            },
                        ],
                    },
                ],
        },
    }
};