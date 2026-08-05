export const normalizeProductOptionValue = (option) => {
    if (typeof option === "string") {
        return option.trim();
    }

    if (option && typeof option === "object") {
        return String(option.value ?? option.name ?? "").trim();
    }

    return "";
};

export const mergeImpactCurveProducts = (appliedProducts = [], pendingProducts = []) => {
    const appliedValues = (Array.isArray(appliedProducts) ? appliedProducts : [])
        .map(normalizeProductOptionValue)
        .filter(Boolean);

    const pendingValues = (Array.isArray(pendingProducts) ? pendingProducts : [])
        .map((value) => normalizeProductOptionValue(value))
        .filter(Boolean);

    const merged = [...appliedValues, ...pendingValues];

    return merged.filter(
        (value, index) => merged.findIndex((candidate) => candidate.toLowerCase() === value.toLowerCase()) === index,
    );
};

export const isProductNameDuplicate = (name, manageProducts = [], appliedProducts = [], pendingProducts = []) => {
    const normalized = normalizeProductOptionValue(name).toLowerCase();

    if (!normalized) {
        return false;
    }

    const existingValues = [
        ...appliedProducts,
        ...pendingProducts,
        ...manageProducts.map((product) => normalizeProductOptionValue(product?.name || product)),
    ]
        .map((value) => normalizeProductOptionValue(value).toLowerCase())
        .filter(Boolean);

    return existingValues.includes(normalized);
};
