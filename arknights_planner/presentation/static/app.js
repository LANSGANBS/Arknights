const state = {
    originalDocument: null,
    currentInventory: {},
    materials: [],
    materialMap: {},
    result: null,
    fullResult: null,
    showFullRanking: false,
    backgroundImages: [],
    backgroundTimer: null,
    activeBackgroundLayer: 0,
    activeBackgroundIndex: 0,
    missingPictureNames: [],
    outputPath: "data/export.json",
};

const elements = {
    bgSlideA: document.getElementById("bgSlideA"),
    bgSlideB: document.getElementById("bgSlideB"),
    statusPanel: document.getElementById("statusPanel"),
    statusLine: document.getElementById("statusLine"),
    resultCards: document.getElementById("resultCards"),
    toggleRankingButton: document.getElementById("toggleRankingButton"),
    inventoryGrid: document.getElementById("inventoryGrid"),
    materialSearch: document.getElementById("materialSearch"),
    loadButton: document.getElementById("loadButton"),
    analyzeButton: document.getElementById("analyzeButton"),
    exportButton: document.getElementById("exportButton"),
    resetButton: document.getElementById("resetButton"),
};

function bindGlassTracking() {
    const root = document.documentElement;
    const updatePointer = (clientX, clientY) => {
        const x = Math.round((clientX / window.innerWidth) * 100);
        const y = Math.round((clientY / window.innerHeight) * 100);
        root.style.setProperty("--glass-x", `${x}%`);
        root.style.setProperty("--glass-y", `${y}%`);
    };

    updatePointer(window.innerWidth * 0.72, window.innerHeight * 0.22);

    window.addEventListener(
        "pointermove",
        (event) => {
            updatePointer(event.clientX, event.clientY);
        },
        { passive: true }
    );

    window.addEventListener("pointerleave", () => {
        updatePointer(window.innerWidth * 0.72, window.innerHeight * 0.22);
    });
}

function setStatus(text, isError = false) {
    elements.statusLine.textContent = text;
    elements.statusLine.dataset.error = isError ? "true" : "false";
    elements.statusPanel.classList.toggle("is-empty", !text);
}

function clearStatus() {
    setStatus("");
}

function inventoryObject() {
    return { ...state.currentInventory };
}

function materialVisual(material, imageClass = "material-icon") {
    if (material?.imageUrl) {
        return `<img class="${imageClass}" src="${encodeURI(material.imageUrl)}" alt="${material.name}" />`;
    }
    return `<span class="${imageClass} placeholder">无图</span>`;
}

function stopBackgroundRotation() {
    if (state.backgroundTimer !== null) {
        window.clearInterval(state.backgroundTimer);
        state.backgroundTimer = null;
    }
}

function backgroundLayer(index) {
    return index === 0 ? elements.bgSlideA : elements.bgSlideB;
}

function setLayerImage(layer, imageUrl) {
    layer.style.backgroundImage = imageUrl ? `url("${encodeURI(imageUrl)}")` : "none";
}

function showBackground(imageIndex, firstPaint = false) {
    const nextImage = state.backgroundImages[imageIndex];
    if (!nextImage) {
        return;
    }

    const nextLayerIndex = firstPaint ? state.activeBackgroundLayer : 1 - state.activeBackgroundLayer;
    const nextLayer = backgroundLayer(nextLayerIndex);
    const currentLayer = backgroundLayer(1 - nextLayerIndex);
    setLayerImage(nextLayer, nextImage);
    nextLayer.classList.add("is-active");
    currentLayer.classList.remove("is-active");
    state.activeBackgroundLayer = nextLayerIndex;
    state.activeBackgroundIndex = imageIndex;
}

function startBackgroundRotation(images) {
    stopBackgroundRotation();
    state.backgroundImages = Array.isArray(images) ? images.filter(Boolean) : [];
    setLayerImage(elements.bgSlideA, "");
    setLayerImage(elements.bgSlideB, "");
    elements.bgSlideA.classList.add("is-active");
    elements.bgSlideB.classList.remove("is-active");
    state.activeBackgroundLayer = 0;
    state.activeBackgroundIndex = 0;

    if (state.backgroundImages.length === 0) {
        return;
    }

    showBackground(0, true);
    if (state.backgroundImages.length === 1) {
        return;
    }

    state.backgroundTimer = window.setInterval(() => {
        const nextIndex = (state.activeBackgroundIndex + 1) % state.backgroundImages.length;
        showBackground(nextIndex);
    }, 16000);
}

function resultSource() {
    return state.showFullRanking && state.fullResult ? state.fullResult : state.result;
}

function syncRankingToggle() {
    const visibleCount = state.result?.shortages?.length || 0;
    const totalCount = state.fullResult?.shortages?.length || 0;
    const expandable = totalCount > visibleCount;
    elements.toggleRankingButton.classList.toggle("is-hidden", !expandable);
    if (!expandable) {
        state.showFullRanking = false;
    }
    elements.toggleRankingButton.textContent = state.showFullRanking ? "收起完整排序" : "展开完整排序";
}

function renderResult() {
    const result = resultSource();
    if (!result) {
        elements.resultCards.innerHTML = "";
        syncRankingToggle();
        return;
    }
    elements.resultCards.innerHTML = "";
    for (const item of result.shortages) {
        const material = state.materialMap[item.item_id];
        const weighted = result.hasWeights ? item.weighted_equivalent.toFixed(2) : "-";
        const card = document.createElement("article");
        card.className = "result-card";
        card.innerHTML = `
            <div class="result-rank">#${item.rank}</div>
            <div class="result-head">
                ${materialVisual(material ?? { id: item.item_id, name: item.name, imageUrl: null }, "result-icon")}
                <div>
                    <strong>${material?.name ?? item.name}</strong>
                    <span>${item.item_id}</span>
                </div>
            </div>
            <dl class="result-metrics">
                <div>
                    <dt>蓝材等效</dt>
                    <dd>${item.blue_equivalent.toFixed(2)}</dd>
                </div>
                <div>
                    <dt>加权后</dt>
                    <dd>${weighted}</dd>
                </div>
            </dl>
        `;
        elements.resultCards.appendChild(card);
    }
    syncRankingToggle();
}

function updateQuantity(itemId, nextValue) {
    const parsed = Number.parseInt(nextValue, 10);
    state.currentInventory[itemId] = Number.isNaN(parsed) ? 0 : Math.max(0, parsed);
}

function renderInventory() {
    const keyword = elements.materialSearch.value.trim().toLowerCase();
    elements.inventoryGrid.innerHTML = "";

    const materials = state.materials.filter((material) => {
        if (!keyword) return true;
        return material.name.toLowerCase().includes(keyword) || material.id.toLowerCase().includes(keyword);
    });

    for (const material of materials) {
        const current = state.currentInventory[material.id] ?? 0;
        const card = document.createElement("article");
        card.className = "material-card";
        card.innerHTML = `
                        <div class="material-tier">T${material.tier}</div>
                        <div class="material-art">${materialVisual(material, "card-image")}</div>
                        <div class="material-meta">
                                <strong>${material.name}</strong>
                                <span>${material.id}</span>
                        </div>
                        <div class="material-quantity">
                                <label>数量</label>
                                <input class="count-input" data-id="${material.id}" type="number" min="0" value="${current}" />
                        </div>
                `;
        elements.inventoryGrid.appendChild(card);
    }

    for (const input of elements.inventoryGrid.querySelectorAll("input.count-input")) {
        input.addEventListener("input", () => {
            updateQuantity(input.dataset.id, input.value);
        });
    }
}

async function bootstrap() {
    clearStatus();
    const response = await fetch("/api/bootstrap");
    const payload = await response.json();
    state.originalDocument = payload.document;
    state.currentInventory = { ...payload.inventory };
    state.materials = payload.materials;
    state.materialMap = Object.fromEntries(payload.materials.map((material) => [material.id, material]));
    state.missingPictureNames = payload.missingPictureNames || [];
    state.outputPath = payload.outputPath || "data/export.json";
    state.result = payload.result;
    state.fullResult = payload.fullResult || payload.result;
    state.showFullRanking = false;
    startBackgroundRotation(payload.backgroundImages || []);
    renderInventory();
    renderResult();
    clearStatus();
}

async function analyze() {
    clearStatus();
    const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inventory: inventoryObject() }),
    });
    const payload = await response.json();
    if (!response.ok) {
        setStatus(payload.error || "分析失败", true);
        return;
    }
    state.result = payload.result;
    state.fullResult = payload.fullResult || payload.result;
    state.showFullRanking = false;
    renderResult();
    clearStatus();
}

async function exportCurrentInventory() {
    clearStatus();
    const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            inventory: inventoryObject(),
            templateDocument: state.originalDocument,
        }),
    });
    const payload = await response.json();
    if (!response.ok) {
        setStatus(payload.error || "导出失败", true);
        return;
    }
    clearStatus();
}

function resetInventory() {
    const original = {};
    for (const entry of state.originalDocument?.items || []) {
        original[entry.id] = entry.have;
    }
    state.currentInventory = original;
    renderInventory();
    clearStatus();
}

elements.loadButton.addEventListener("click", () => {
    bootstrap().catch((error) => setStatus(error.message || "导入失败", true));
});
elements.analyzeButton.addEventListener("click", () => {
    analyze().catch((error) => setStatus(error.message || "分析失败", true));
});
elements.exportButton.addEventListener("click", () => {
    exportCurrentInventory().catch((error) => setStatus(error.message || "导出失败", true));
});
elements.resetButton.addEventListener("click", resetInventory);
elements.toggleRankingButton.addEventListener("click", () => {
    state.showFullRanking = !state.showFullRanking;
    renderResult();
});
elements.materialSearch.addEventListener("input", renderInventory);

bindGlassTracking();
bootstrap().catch((error) => setStatus(error.message || "初始化失败", true));
