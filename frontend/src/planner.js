import { BLUE_MATERIAL_IDS, CRAFTING_RULES, MATERIALS, UPGRADE_RULES } from "./plannerData";

export const EMPTY_DOCUMENT = {
    "@type": "@penguin-statistics/planner/config",
    items: [],
    options: {},
    excludes: [],
};

const normalizationCache = new Map();

function cloneJson(value, fallback) {
    if (value == null) {
        return fallback;
    }
    return JSON.parse(JSON.stringify(value));
}

function normalizePairs(itemId) {
    if (normalizationCache.has(itemId)) {
        return normalizationCache.get(itemId);
    }
    const definition = MATERIALS[itemId];
    if (!definition) {
        throw new Error(`未知材料 ID: ${itemId}`);
    }

    let result;
    if (definition.tier === 3) {
        result = [[itemId, 1]];
    } else if (definition.tier < 3) {
        const upgrade = UPGRADE_RULES[itemId];
        if (!upgrade) {
            throw new Error(`材料 ${itemId} 缺少向上折算规则，无法换算到蓝材。`);
        }
        const [targetItemId, targetCost] = upgrade;
        result = normalizePairs(targetItemId)
            .map(([blueItemId, value]) => [blueItemId, value / targetCost])
            .sort(([leftId], [rightId]) => leftId.localeCompare(rightId));
    } else {
        const rule = CRAFTING_RULES[itemId];
        if (!rule) {
            throw new Error(`材料 ${itemId} 缺少折算规则，无法换算到蓝材。`);
        }
        const totals = {};
        for (const [costItemId, costCount] of Object.entries(rule)) {
            for (const [blueItemId, blueValue] of normalizePairs(costItemId)) {
                totals[blueItemId] = (totals[blueItemId] || 0) + blueValue * costCount;
            }
        }
        result = Object.entries(totals).sort(([leftId], [rightId]) => leftId.localeCompare(rightId));
    }

    normalizationCache.set(itemId, result);
    return result;
}

function resolveWeightFactors(weights) {
    if (!weights || Object.keys(weights).length === 0) {
        return {
            factors: Object.fromEntries(BLUE_MATERIAL_IDS.map((itemId) => [itemId, 1])),
            hasWeights: false,
        };
    }

    const selected = Object.fromEntries(
        Object.entries(weights).filter(([itemId, value]) => BLUE_MATERIAL_IDS.includes(itemId) && Number(value) > 0)
    );
    const values = Object.values(selected);
    if (values.length === 0) {
        return {
            factors: Object.fromEntries(BLUE_MATERIAL_IDS.map((itemId) => [itemId, 1])),
            hasWeights: false,
        };
    }

    const baseline = values.reduce((sum, value) => sum + value, 0) / values.length;
    const factors = Object.fromEntries(BLUE_MATERIAL_IDS.map((itemId) => [itemId, 1]));
    for (const [itemId, value] of Object.entries(selected)) {
        factors[itemId] = value / baseline;
    }

    return { factors, hasWeights: true };
}

export function documentToInventory(document) {
    const items = Array.isArray(document?.items) ? document.items : [];
    const inventory = {};
    for (const entry of items) {
        if (!entry || typeof entry !== "object") {
            continue;
        }
        const itemId = String(entry.id || "").trim();
        if (!itemId) {
            continue;
        }
        const have = Number.parseInt(entry.have ?? 0, 10);
        inventory[itemId] = (inventory[itemId] || 0) + (Number.isNaN(have) ? 0 : have);
    }
    return inventory;
}

export function parseInventoryFile(text) {
    const raw = JSON.parse(text);
    const document = Array.isArray(raw)
        ? {
              ...EMPTY_DOCUMENT,
              items: raw,
          }
        : {
              "@type": raw?.["@type"] || EMPTY_DOCUMENT["@type"],
              items: Array.isArray(raw?.items) ? raw.items : [],
              options: raw?.options && typeof raw.options === "object" ? raw.options : {},
              excludes: Array.isArray(raw?.excludes) ? raw.excludes : [],
          };

    if (!Array.isArray(document.items)) {
        throw new Error("导入文件必须是 JSON 对象或 items 数组。");
    }

    return {
        document,
        inventory: documentToInventory(document),
    };
}

export function parseWeightEntries(raw) {
    if (!Array.isArray(raw)) {
        throw new Error("权重文件必须是数组格式。");
    }

    const weights = {};
    for (const entry of raw) {
        if (!entry || typeof entry !== "object") {
            continue;
        }
        const itemId = String(entry.id || "").trim();
        if (!itemId || !BLUE_MATERIAL_IDS.includes(itemId)) {
            continue;
        }
        if (entry.apValue == null) {
            continue;
        }
        const value = Number(entry.apValue);
        if (!Number.isFinite(value)) {
            continue;
        }
        weights[itemId] = value;
    }
    return Object.keys(weights).length > 0 ? weights : null;
}

export function parseWeightFile(text) {
    return parseWeightEntries(JSON.parse(text));
}

export function buildInventoryDocument(inventory, template = EMPTY_DOCUMENT) {
    const base = {
        "@type": template?.["@type"] || EMPTY_DOCUMENT["@type"],
        items: [],
        options: template?.options && typeof template.options === "object" ? cloneJson(template.options, {}) : {},
        excludes: Array.isArray(template?.excludes) ? cloneJson(template.excludes, []) : [],
    };

    const orderedIds = [];
    if (Array.isArray(template?.items)) {
        for (const entry of template.items) {
            if (!entry || typeof entry !== "object") {
                continue;
            }
            const itemId = String(entry.id || "").trim();
            if (itemId && !orderedIds.includes(itemId)) {
                orderedIds.push(itemId);
            }
        }
    }

    for (const itemId of Object.keys(inventory).sort()) {
        if (!orderedIds.includes(itemId)) {
            orderedIds.push(itemId);
        }
    }

    base.items = orderedIds.map((itemId) => ({
        id: itemId,
        have: Math.max(0, Number.parseInt(inventory[itemId] ?? 0, 10) || 0),
    }));
    return base;
}

export function planInventory(inventory, { topN = 5, weights = null } = {}) {
    const unknownItemIds = Object.keys(inventory)
        .filter((itemId) => !MATERIALS[itemId])
        .sort();
    const blueTotals = Object.fromEntries(BLUE_MATERIAL_IDS.map((itemId) => [itemId, 0]));

    for (const [itemId, count] of Object.entries(inventory)) {
        if (!MATERIALS[itemId] || Number(count) === 0) {
            continue;
        }
        for (const [blueItemId, blueCount] of normalizePairs(itemId)) {
            blueTotals[blueItemId] += Number(count) * blueCount;
        }
    }

    const { factors, hasWeights } = resolveWeightFactors(weights);
    const shortages = BLUE_MATERIAL_IDS.map((itemId) => {
        const blueEquivalent = blueTotals[itemId];
        const weightFactor = factors[itemId];
        return {
            rank: 0,
            item_id: itemId,
            name: MATERIALS[itemId].name,
            blue_equivalent: blueEquivalent,
            weight_factor: weightFactor,
            weighted_equivalent: blueEquivalent / weightFactor,
        };
    }).sort((left, right) => {
        if (left.weighted_equivalent !== right.weighted_equivalent) {
            return left.weighted_equivalent - right.weighted_equivalent;
        }
        if (left.blue_equivalent !== right.blue_equivalent) {
            return left.blue_equivalent - right.blue_equivalent;
        }
        const nameCompare = left.name.localeCompare(right.name, "zh-Hans-CN");
        if (nameCompare !== 0) {
            return nameCompare;
        }
        return left.item_id.localeCompare(right.item_id);
    });

    return {
        hasWeights,
        shortages: shortages.slice(0, topN).map((item, index) => ({
            ...item,
            rank: index + 1,
        })),
        unknownItemIds,
    };
}
