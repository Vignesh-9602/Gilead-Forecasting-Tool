export const mockData = {
    total_market_volume: {
        market_volume: {
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
                        label: "BASE",

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
                        label: "BASE",

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

        market_share: {
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
                        label: "Market Share",

                        history: [
                            100,
                            100,
                            100,
                            100,
                            100,
                            100,
                            100,
                            100,
                        ],

                        forecast: [
                            100,
                            100,
                            100,
                            100,
                        ],
                    },
                ],
            },

            table: {
                type: "flat",

                rows: [
                    {
                        label: "Market Share",

                        values: [
                            100,
                            100,
                            100,
                            100,
                            100,
                            100,
                            100,
                            100,
                            100,
                            100,
                            100,
                            100,
                        ],
                    },
                ],
            },
        },
    },

    market_distribution: {
        market_volume: {
            unit: "count",

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
                type: "hierarchy",

                rows: [
                    {
                        label: "Overall",
                        values: [
                            32000, 33500, 34800, 36000,
                            38200, 39500, 41000, 42500,
                            43800, 45200, 47000, 48800,
                        ],
                    },

                    {
                        label: "Retail",
                        values: [
                            22000, 22800, 23600, 24500,
                            25500, 26200, 27000, 27800,
                            28600, 29400, 30200, 31000,
                        ],
                    },

                    {
                        label: "Non Retail",

                        values: [
                            10000, 10700, 11200, 11500,
                            12700, 13300, 14000, 14700,
                            15200, 15800, 16800, 17800,
                        ],

                        children: [
                            {
                                label: "Kaiser",

                                values: [
                                    3500, 3745, 3920, 4025,
                                    4445, 4655, 4900, 5145,
                                    5320, 5530, 5880, 6230,
                                ],
                            },

                            {
                                label: "IQVIA",

                                values: [
                                    3000, 3210, 3360, 3450,
                                    3810, 3990, 4200, 4410,
                                    4560, 4740, 5040, 5340,
                                ],
                            },

                            {
                                label: "ADAP",

                                values: [
                                    2000, 2140, 2240, 2300,
                                    2540, 2660, 2800, 2940,
                                    3040, 3160, 3360, 3560,
                                ],
                            },

                            {
                                label: "Federal",

                                values: [
                                    1500, 1605, 1680, 1725,
                                    1905, 1995, 2100, 2205,
                                    2280, 2370, 2520, 2670,
                                ],
                            },
                        ],
                    },
                ],
            },
        },

        market_share: {
            unit: "%",

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
                            68.75,
                            68.06,
                            67.82,
                            68.06,
                            66.75,
                            66.33,
                            65.85,
                            65.41,
                        ],

                        forecast: [
                            65.30,
                            65.04,
                            64.26,
                            63.52,
                        ],
                    },

                    {
                        label: "Non Retail",

                        history: [
                            31.25,
                            31.94,
                            32.18,
                            31.94,
                            33.25,
                            33.67,
                            34.15,
                            34.59,
                        ],

                        forecast: [
                            34.70,
                            34.96,
                            35.74,
                            36.48,
                        ],
                    },
                ],
            },

            table: {
                type: "hierarchy",

                rows: [
                    {
                        label: "Overall",
                        values: [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
                    },

                    {
                        label: "Retail",
                        values: [
                            68.75, 68.06, 67.82, 68.06,
                            66.75, 66.33, 65.85, 65.41,
                            65.30, 65.04, 64.26, 63.52,
                        ],
                    },

                    {
                        label: "Non Retail",

                        values: [
                            31.25, 31.94, 32.18, 31.94,
                            33.25, 33.67, 34.15, 34.59,
                            34.70, 34.96, 35.74, 36.48,
                        ],

                        children: [
                            {
                                label: "Kaiser",
                                values: [35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35],
                            },

                            {
                                label: "IQVIA",
                                values: [30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
                            },

                            {
                                label: "ADAP",
                                values: [20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20],
                            },

                            {
                                label: "Federal",
                                values: [15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15],
                            },
                        ],
                    },
                ],
            },
        },
    },

    product_distribution: {
        market_volume: {
            unit: "count",

            chart: {
                months: [
                    "Jan-24", "Feb-24", "Mar-24", "Apr-24", "May-24", "Jun-24",
                    "Jul-24", "Aug-24", "Sep-24", "Oct-24", "Nov-24", "Dec-24"
                ],

                forecast_start_index: 8,

                series: [
                    {
                        label: "Truvada",
                        history: [
                            12160, 13065, 13224, 13320, 14134, 14220, 14350, 14450
                        ],
                        forecast: [
                            14892, 14916, 15510, 15616
                        ],
                    },
                    {
                        label: "Descovy",
                        history: [
                            8960, 9715, 10440, 10800, 11842, 12245, 13120, 14025
                        ],
                        forecast: [
                            14892, 15368, 16450, 17080
                        ],
                    },
                    {
                        label: "Biktarvy",
                        history: [
                            10880, 10720, 11136, 11880, 12224, 13035, 13530, 14025
                        ],
                        forecast: [
                            14016, 14916, 15040, 16104
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
                            32000, 33500, 34800, 36000,
                            38200, 39500, 41000, 42500,
                            43800, 45200, 47000, 48800
                        ],
                    },

                    {
                        label: "Truvada",
                        values: [
                            12160, 13065, 13224, 13320,
                            14134, 14220, 14350, 14450,
                            14892, 14916, 15510, 15616
                        ],
                    },

                    {
                        label: "Descovy",
                        values: [
                            8960, 9715, 10440, 10800,
                            11842, 12245, 13120, 14025,
                            14892, 15368, 16450, 17080
                        ],
                    },

                    {
                        label: "Biktarvy",
                        values: [
                            10880, 10720, 11136, 11880,
                            12224, 13035, 13530, 14025,
                            14016, 14916, 15040, 16104
                        ],
                    },
                ],
            },
        },

        market_share: {
            unit: "%",

            chart: {
                months: [
                    "Jan-24", "Feb-24", "Mar-24", "Apr-24", "May-24", "Jun-24",
                    "Jul-24", "Aug-24", "Sep-24", "Oct-24", "Nov-24", "Dec-24"
                ],

                forecast_start_index: 8,

                series: [
                    {
                        label: "Truvada",
                        history: [38, 39, 38, 37, 37, 36, 35, 34],
                        forecast: [34, 33, 33, 32],
                    },

                    {
                        label: "Descovy",
                        history: [28, 29, 30, 30, 31, 31, 32, 33],
                        forecast: [34, 34, 35, 35],
                    },

                    {
                        label: "Biktarvy",
                        history: [34, 32, 32, 33, 32, 33, 33, 33],
                        forecast: [32, 33, 32, 33],
                    },
                ],
            },

            table: {
                type: "flat",

                rows: [
                    {
                        label: "Overall",
                        values: [
                            100, 100, 100, 100,
                            100, 100, 100, 100,
                            100, 100, 100, 100
                        ],
                    },

                    {
                        label: "Truvada",
                        values: [
                            38, 39, 38, 37,
                            37, 36, 35, 34,
                            34, 33, 33, 32
                        ],
                    },

                    {
                        label: "Descovy",
                        values: [
                            28, 29, 30, 30,
                            31, 31, 32, 33,
                            34, 34, 35, 35
                        ],
                    },

                    {
                        label: "Biktarvy",
                        values: [
                            34, 32, 32, 33,
                            32, 33, 33, 33,
                            32, 33, 32, 33
                        ],
                    },
                ],
            },
        },
    },

    market_product: {
        market_volume: {
            unit: "count",

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

            table: {
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
                                values: [
                                    9000,
                                    9300,
                                    9500,
                                    9800,
                                    10100,
                                    10400,
                                    10700,
                                    11000,
                                    11200,
                                    11400,
                                    11600,
                                    11800,
                                ],
                            },
                            {
                                label: "Descovy",
                                values: [
                                    6000,
                                    6200,
                                    6400,
                                    6600,
                                    6800,
                                    7000,
                                    7200,
                                    7400,
                                    7600,
                                    7800,
                                    8000,
                                    8200,
                                ],
                            },
                            {
                                label: "Biktarvy",
                                values: [
                                    7000,
                                    7300,
                                    7600,
                                    8100,
                                    8600,
                                    8800,
                                    9100,
                                    9400,
                                    9800,
                                    10000,
                                    10400,
                                    10800,
                                ],
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
                                values: [
                                    3200,
                                    3300,
                                    3400,
                                    3500,
                                    3600,
                                    3700,
                                    3800,
                                    3900,
                                    4000,
                                    4100,
                                    4200,
                                    4300,
                                ],
                            },
                            {
                                label: "Descovy",
                                values: [
                                    2900,
                                    3000,
                                    3100,
                                    3200,
                                    3300,
                                    3400,
                                    3500,
                                    3600,
                                    3700,
                                    3800,
                                    3900,
                                    4000,
                                ],
                            },
                            {
                                label: "Biktarvy",
                                values: [
                                    3900,
                                    4100,
                                    4300,
                                    4450,
                                    4800,
                                    5100,
                                    5400,
                                    5700,
                                    5800,
                                    6200,
                                    6500,
                                    6800,
                                ],
                            },
                        ],
                    },
                ],
            },
        },

        market_share: {
            unit: "%",

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
                        history: [40.91, 40.79, 40.43, 40.00, 39.61, 39.69, 39.63, 39.57],
                        forecast: [39.16, 39.04, 38.67, 38.31],
                    },
                    {
                        label: "Retail - Descovy",
                        history: [27.27, 27.19, 27.23, 26.94, 26.67, 26.72, 26.67, 26.62],
                        forecast: [26.57, 26.71, 26.67, 26.62],
                    },
                    {
                        label: "Retail - Biktarvy",
                        history: [31.82, 32.02, 32.34, 33.06, 33.73, 33.59, 33.70, 33.81],
                        forecast: [34.27, 34.25, 34.67, 35.06],
                    },
                    // {
                    //     label: "Non Retail - Truvada",
                    //     history: [32.00, 31.73, 31.48, 31.39, 30.77, 30.33, 29.92, 29.55],
                    //     forecast: [29.63, 29.08, 28.77, 28.48],
                    // },
                    // {
                    //     label: "Non Retail - Descovy",
                    //     history: [29.00, 28.85, 28.70, 28.70, 28.21, 27.87, 27.56, 27.27],
                    //     forecast: [27.41, 26.95, 26.71, 26.49],
                    // },
                    // {
                    //     label: "Non Retail - Biktarvy",
                    //     history: [39.00, 39.42, 39.81, 39.91, 41.03, 41.80, 42.52, 43.18],
                    //     forecast: [42.96, 43.97, 44.52, 45.03],
                    // },
                ],
            },

            table: {
                type: "hierarchy",

                rows: [
                    {
                        label: "Retail",

                        values: [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],

                        children: [
                            {
                                label: "Truvada",
                                values: [
                                    40.91,
                                    40.79,
                                    40.43,
                                    40.00,
                                    39.61,
                                    39.69,
                                    39.63,
                                    39.57,
                                    39.16,
                                    39.04,
                                    38.67,
                                    38.31,
                                ],
                            },
                            {
                                label: "Descovy",
                                values: [
                                    27.27,
                                    27.19,
                                    27.23,
                                    26.94,
                                    26.67,
                                    26.72,
                                    26.67,
                                    26.62,
                                    26.57,
                                    26.71,
                                    26.67,
                                    26.62,
                                ],
                            },
                            {
                                label: "Biktarvy",
                                values: [
                                    31.82,
                                    32.02,
                                    32.34,
                                    33.06,
                                    33.73,
                                    33.59,
                                    33.70,
                                    33.81,
                                    34.27,
                                    34.25,
                                    34.67,
                                    35.06,
                                ],
                            },
                        ],
                    },

                    {
                        label: "Non Retail",

                        values: [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],

                        children: [
                            {
                                label: "Truvada",
                                values: [
                                    32.00,
                                    31.73,
                                    31.48,
                                    31.39,
                                    30.77,
                                    30.33,
                                    29.92,
                                    29.55,
                                    29.63,
                                    29.08,
                                    28.77,
                                    28.48,
                                ],
                            },
                            {
                                label: "Descovy",
                                values: [
                                    29.00,
                                    28.85,
                                    28.70,
                                    28.70,
                                    28.21,
                                    27.87,
                                    27.56,
                                    27.27,
                                    27.41,
                                    26.95,
                                    26.71,
                                    26.49,
                                ],
                            },
                            {
                                label: "Biktarvy",
                                values: [
                                    39.00,
                                    39.42,
                                    39.81,
                                    39.91,
                                    41.03,
                                    41.80,
                                    42.52,
                                    43.18,
                                    42.96,
                                    43.97,
                                    44.52,
                                    45.03,
                                ],
                            },
                        ],
                    },
                ],
            },
        },

    },

    product_market: {
        market_volume: {
            unit: "count",

            chart: {
                months: [
                    "Jan-24", "Feb-24", "Mar-24", "Apr-24", "May-24", "Jun-24",
                    "Jul-24", "Aug-24", "Sep-24", "Oct-24", "Nov-24", "Dec-24",
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

                rows: [
                    {
                        label: "Truvada",

                        values: [
                            12200, 12600, 12900, 13300,
                            13700, 14100, 14500, 14900,
                            15200, 15500, 15800, 16100,
                        ],

                        children: [
                            {
                                label: "Retail",
                                values: [
                                    9000, 9300, 9500, 9800,
                                    10100, 10400, 10700, 11000,
                                    11200, 11400, 11600, 11800,
                                ],
                            },
                            {
                                label: "Non Retail",
                                values: [
                                    3200, 3300, 3400, 3500,
                                    3600, 3700, 3800, 3900,
                                    4000, 4100, 4200, 4300,
                                ],
                            },
                        ],
                    },

                    {
                        label: "Descovy",

                        values: [
                            8900, 9200, 9500, 9800,
                            10100, 10400, 10700, 11000,
                            11300, 11600, 11900, 12200,
                        ],

                        children: [
                            {
                                label: "Retail",
                                values: [
                                    6000, 6200, 6400, 6600,
                                    6800, 7000, 7200, 7400,
                                    7600, 7800, 8000, 8200,
                                ],
                            },
                            {
                                label: "Non Retail",
                                values: [
                                    2900, 3000, 3100, 3200,
                                    3300, 3400, 3500, 3600,
                                    3700, 3800, 3900, 4000,
                                ],
                            },
                        ],
                    },

                    {
                        label: "Biktarvy",

                        values: [
                            10900, 11400, 11900, 12550,
                            13400, 13900, 14500, 15100,
                            15600, 16200, 16900, 17600,
                        ],

                        children: [
                            {
                                label: "Retail",
                                values: [
                                    7000, 7300, 7600, 8100,
                                    8600, 8800, 9100, 9400,
                                    9800, 10000, 10400, 10800,
                                ],
                            },
                            {
                                label: "Non Retail",
                                values: [
                                    3900, 4100, 4300, 4450,
                                    4800, 5100, 5400, 5700,
                                    5800, 6200, 6500, 6800,
                                ],
                            },
                        ],
                    },
                ],
            },
        },

        market_share: {
            unit: "%",

            chart: {
                months: [
                    "Jan-24", "Feb-24", "Mar-24", "Apr-24", "May-24", "Jun-24",
                    "Jul-24", "Aug-24", "Sep-24", "Oct-24", "Nov-24", "Dec-24",
                ],

                forecast_start_index: 8,

                series: [
                    {
                        label: "Truvada - Retail",
                        history: [73.77, 73.81, 73.64, 73.68, 73.72, 73.76, 73.79, 73.83],
                        forecast: [73.68, 73.55, 73.42, 73.29],
                    },
                    {
                        label: "Truvada - Non Retail",
                        history: [26.23, 26.19, 26.36, 26.32, 26.28, 26.24, 26.21, 26.17],
                        forecast: [26.32, 26.45, 26.58, 26.71],
                    },

                    // {
                    //     label: "Descovy - Retail",
                    //     history: [67.42, 67.39, 67.37, 67.35, 67.33, 67.31, 67.29, 67.27],
                    //     forecast: [67.26, 67.24, 67.23, 67.21],
                    // },
                    // {
                    //     label: "Descovy - Non Retail",
                    //     history: [32.58, 32.61, 32.63, 32.65, 32.67, 32.69, 32.71, 32.73],
                    //     forecast: [32.74, 32.76, 32.77, 32.79],
                    // },

                    // {
                    //     label: "Biktarvy - Retail",
                    //     history: [64.22, 64.04, 63.87, 64.54, 64.18, 63.31, 62.76, 62.25],
                    //     forecast: [62.82, 61.73, 61.54, 61.36],
                    // },
                    // {
                    //     label: "Biktarvy - Non Retail",
                    //     history: [35.78, 35.96, 36.13, 35.46, 35.82, 36.69, 37.24, 37.75],
                    //     forecast: [37.18, 38.27, 38.46, 38.64],
                    // },
                ],
            },

            table: {
                type: "hierarchy",

                rows: [
                    {
                        label: "Truvada",
                        values: [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],

                        children: [
                            {
                                label: "Retail",
                                values: [73.77, 73.81, 73.64, 73.68, 73.72, 73.76, 73.79, 73.83, 73.68, 73.55, 73.42, 73.29],
                            },
                            {
                                label: "Non Retail",
                                values: [26.23, 26.19, 26.36, 26.32, 26.28, 26.24, 26.21, 26.17, 26.32, 26.45, 26.58, 26.71],
                            },
                        ],
                    },

                    {
                        label: "Descovy",
                        values: [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],

                        children: [
                            {
                                label: "Retail",
                                values: [67.42, 67.39, 67.37, 67.35, 67.33, 67.31, 67.29, 67.27, 67.26, 67.24, 67.23, 67.21],
                            },
                            {
                                label: "Non Retail",
                                values: [32.58, 32.61, 32.63, 32.65, 32.67, 32.69, 32.71, 32.73, 32.74, 32.76, 32.77, 32.79],
                            },
                        ],
                    },

                    {
                        label: "Biktarvy",
                        values: [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],

                        children: [
                            {
                                label: "Retail",
                                values: [64.22, 64.04, 63.87, 64.54, 64.18, 63.31, 62.76, 62.25, 62.82, 61.73, 61.54, 61.36],
                            },
                            {
                                label: "Non Retail",
                                values: [35.78, 35.96, 36.13, 35.46, 35.82, 36.69, 37.24, 37.75, 37.18, 38.27, 38.46, 38.64],
                            },
                        ],
                    },
                ],
            },
        },
    },
};