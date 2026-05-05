import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import LiquidGlass from "liquid-glass-react";
import defaultWeightEntries from "../../data/weight.json";
import { BACKGROUND_IMAGES, MATERIAL_IMAGE_MAP } from "./assets";
import { sampleMaaDocument, samplePenguinDocument } from "./inventoryExamples";
import { buildInventoryDocument, EMPTY_DOCUMENT, parseInventoryFile, parseWeightEntries, parseWeightFile, planInventory } from "./planner";
import { BLUE_MATERIAL_IDS, MATERIAL_LIST } from "./plannerData";

const DEFAULT_TOP_N = 5;

const BUTTON_GLASS = {
    mode: "shader",
    blurAmount: 0.06,
    saturation: 136,
    displacementScale: 124,
    aberrationIntensity: 2.8,
    elasticity: 0,
    cornerRadius: 22,
    padding: "0px",
    overLight: false,
};

const CONFIRMATION_COPY = {
    reset: {
        title: "确认重置",
        description: "这会把当前页面上的所有素材数量直接清零。",
        confirmText: "确认重置",
    },
};

const INVENTORY_EXAMPLES = {
    maa: {
        title: "MAA JSON 示例",
        description: "这是当前项目内置的 MAA 仓库识别导出示例，导入时会自动过滤无关项并转成内部企鹅物流格式。",
        content: JSON.stringify(sampleMaaDocument, null, 2),
        fileName: "export_maa.json",
    },
    penguin: {
        title: "企鹅物流 JSON 示例",
        description: "这是当前项目内置的企鹅物流规划器库存示例，网页会直接按原格式解析。",
        content: JSON.stringify(samplePenguinDocument, null, 2),
        fileName: "export_penguin.json",
    },
};

function createPlanState(inventory, weights) {
    const result = planInventory(inventory, { topN: DEFAULT_TOP_N, weights });
    const fullResult = planInventory(inventory, { topN: BLUE_MATERIAL_IDS.length, weights });
    return { result, fullResult };
}

function MaterialImage({ material, className }) {
    if (material?.imageUrl) {
        return <img className={className} src={material.imageUrl} alt={material.name} />;
    }
    return <span className={`${className} placeholder`}>无图</span>;
}

function LiquidAction({ className = "", onClick, children, mouseContainerRef }) {
    const [isPressed, setIsPressed] = useState(false);

    return (
        <div
            className={`liquid-button-shell ${className} ${isPressed ? "is-pressed" : ""}`.trim()}
            onPointerDown={() => setIsPressed(true)}
            onPointerUp={() => setIsPressed(false)}
            onPointerLeave={() => setIsPressed(false)}
            onPointerCancel={() => setIsPressed(false)}
        >
            <LiquidGlass
                {...BUTTON_GLASS}
                mouseContainer={mouseContainerRef}
                className="liquid-button"
                onClick={onClick}
                style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%" }}
            >
                <div className="liquid-button__inner">{children}</div>
            </LiquidGlass>
        </div>
    );
}

async function readSelectedFile(event) {
    const file = event.target.files?.[0] || null;
    event.target.value = "";
    if (!file) {
        return null;
    }
    return {
        file,
        text: await file.text(),
    };
}

function downloadJson(jsonDocument, fileName) {
    const blob = new Blob([JSON.stringify(jsonDocument, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    window.document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
}

function shuffleArray(items) {
    const nextItems = [...items];
    for (let index = nextItems.length - 1; index > 0; index -= 1) {
        const swapIndex = Math.floor(Math.random() * (index + 1));
        [nextItems[index], nextItems[swapIndex]] = [nextItems[swapIndex], nextItems[index]];
    }
    return nextItems;
}

export default function App() {
    const mouseContainerRef = useRef(null);
    const inventoryInputRef = useRef(null);
    const weightInputRef = useRef(null);
    const backgroundIndexRef = useRef(0);

    const defaultWeights = useMemo(() => parseWeightEntries(defaultWeightEntries), []);
    const initialPlan = useMemo(() => createPlanState({}, defaultWeights), [defaultWeights]);
    const backgroundSequence = useMemo(() => shuffleArray(BACKGROUND_IMAGES), []);
    const [originalDocument, setOriginalDocument] = useState(EMPTY_DOCUMENT);
    const [inventory, setInventory] = useState({});
    const [weights, setWeights] = useState(defaultWeights);
    const [inventoryFileName, setInventoryFileName] = useState("");
    const [weightFileName, setWeightFileName] = useState("内置默认权重");
    const [result, setResult] = useState(initialPlan.result);
    const [fullResult, setFullResult] = useState(initialPlan.fullResult);
    const [showFullRanking, setShowFullRanking] = useState(false);
    const [backgroundState, setBackgroundState] = useState({ active: 0, indexes: [0, 0] });
    const [searchText, setSearchText] = useState("");
    const [pendingAction, setPendingAction] = useState(null);
    const [examplePreviewKey, setExamplePreviewKey] = useState(null);
    const deferredSearchText = useDeferredValue(searchText);

    const materials = useMemo(
        () => MATERIAL_LIST.map((material) => ({ ...material, imageUrl: MATERIAL_IMAGE_MAP[material.name] || null })),
        []
    );

    const materialMap = useMemo(() => Object.fromEntries(materials.map((material) => [material.id, material])), [materials]);
    const hasInventoryValues = useMemo(
        () => Object.values(inventory).some((value) => Number(value) > 0),
        [inventory]
    );

    const filteredMaterials = useMemo(() => {
        const keyword = deferredSearchText.trim().toLowerCase();
        if (!keyword) {
            return materials;
        }
        return materials.filter(
            (material) => material.name.toLowerCase().includes(keyword) || material.id.toLowerCase().includes(keyword)
        );
    }, [materials, deferredSearchText]);

    const canExpand = hasInventoryValues && (fullResult?.shortages?.length || 0) > (result?.shortages?.length || 0);
    const activeResult = showFullRanking && fullResult ? fullResult : result;
    const visibleShortages = hasInventoryValues ? activeResult?.shortages || [] : [];

    useEffect(() => {
        setBackgroundState({ active: 0, indexes: [0, 0] });
        backgroundIndexRef.current = 0;
        if (backgroundSequence.length === 0) {
            return undefined;
        }

        let timer = null;
        let cancelled = false;

        const preloadImage = (imageUrl) =>
            new Promise((resolve) => {
                if (!imageUrl) {
                    resolve(false);
                    return;
                }
                const image = new window.Image();
                let finished = false;
                const complete = (success) => {
                    if (finished) {
                        return;
                    }
                    finished = true;
                    resolve(success);
                };
                image.onload = () => complete(true);
                image.onerror = () => complete(false);
                image.src = imageUrl;
                if (image.complete && image.naturalWidth > 0) {
                    complete(true);
                }
            });

        const showBackground = async (nextIndex, firstPaint = false) => {
            const loaded = await preloadImage(backgroundSequence[nextIndex]);
            if (!loaded || cancelled) {
                return false;
            }
            setBackgroundState((prev) => {
                if (firstPaint) {
                    return { active: 0, indexes: [nextIndex, nextIndex] };
                }
                const nextActive = prev.active === 0 ? 1 : 0;
                const nextIndexes = [...prev.indexes];
                nextIndexes[nextActive] = nextIndex;
                return { active: nextActive, indexes: nextIndexes };
            });
            return true;
        };

        const scheduleNext = () => {
            if (backgroundSequence.length <= 1 || cancelled) {
                return;
            }
            timer = window.setTimeout(async () => {
                const nextIndex = (backgroundIndexRef.current + 1) % backgroundSequence.length;
                const switched = await showBackground(nextIndex);
                if (switched) {
                    backgroundIndexRef.current = nextIndex;
                }
                scheduleNext();
            }, 16000);
        };

        void showBackground(0, true).then((switched) => {
            if (switched) {
                backgroundIndexRef.current = 0;
            }
            scheduleNext();
        });

        return () => {
            cancelled = true;
            if (timer !== null) {
                window.clearTimeout(timer);
            }
        };
    }, [backgroundSequence]);

    const applyPlan = (nextInventory, nextWeights) => {
        const nextPlan = createPlanState(nextInventory, nextWeights);
        setResult(nextPlan.result);
        setFullResult(nextPlan.fullResult);
        setShowFullRanking(false);
    };

    const analyze = () => {
        try {
            applyPlan(inventory, weights);
        } catch (error) {
            window.alert(error.message || "分析失败");
        }
    };

    const importInventory = async (event) => {
        try {
            const payload = await readSelectedFile(event);
            if (!payload) {
                return;
            }
            const parsed = parseInventoryFile(payload.text);
            setOriginalDocument(parsed.document);
            setInventory(parsed.inventory);
            setInventoryFileName(`${payload.file.name} · ${parsed.sourceFormat === "maa" ? "MAA" : "企鹅物流"}`);
            applyPlan(parsed.inventory, weights);
        } catch (error) {
            window.alert(error.message || "导入库存失败");
        }
    };

    const importWeight = async (event) => {
        try {
            const payload = await readSelectedFile(event);
            if (!payload) {
                return;
            }
            const nextWeights = parseWeightFile(payload.text);
            setWeights(nextWeights);
            setWeightFileName(payload.file.name);
            applyPlan(inventory, nextWeights);
        } catch (error) {
            window.alert(error.message || "导入权重失败");
        }
    };

    const exportInventory = () => {
        try {
            const nextDocument = buildInventoryDocument(inventory, originalDocument);
            downloadJson(nextDocument, "export_penguin.json");
        } catch (error) {
            window.alert(error.message || "导出失败");
        }
    };

    const resetInventory = () => {
        const nextInventory = {};
        for (const material of materials) {
            nextInventory[material.id] = 0;
        }
        setInventory(nextInventory);
        applyPlan(nextInventory, weights);
    };

    const normalizeQuantity = (value) => {
        const parsed = Number.parseInt(value, 10);
        return Number.isNaN(parsed) ? 0 : Math.max(0, parsed);
    };

    const updateQuantity = (itemId, value) => {
        setInventory((current) => ({
            ...current,
            [itemId]: normalizeQuantity(value),
        }));
    };

    const handleQuantityInput = (itemId, value) => {
        const digitsOnly = value.replace(/\D+/g, "");
        updateQuantity(itemId, digitsOnly);
    };

    const openConfirmation = (action) => {
        setPendingAction(action);
    };

    const closeConfirmation = () => {
        setPendingAction(null);
    };

    const openInventoryExample = (exampleKey) => {
        setExamplePreviewKey(exampleKey);
    };

    const closeInventoryExample = () => {
        setExamplePreviewKey(null);
    };

    const confirmPendingAction = () => {
        if (pendingAction === "reset") {
            resetInventory();
        }
        setPendingAction(null);
    };

    const pendingCopy = pendingAction ? CONFIRMATION_COPY[pendingAction] : null;
    const examplePreview = examplePreviewKey ? INVENTORY_EXAMPLES[examplePreviewKey] : null;

    return (
        <div className="page-shell" ref={mouseContainerRef}>
            <input ref={inventoryInputRef} className="hidden-file-input" type="file" accept=".json,application/json" onChange={importInventory} />
            <input ref={weightInputRef} className="hidden-file-input" type="file" accept=".json,application/json" onChange={importWeight} />

            <div className="background-stage" aria-hidden="true">
                <div
                    className={`bg-slide ${backgroundState.active === 0 ? "is-active" : ""}`}
                    style={{ backgroundImage: backgroundSequence[backgroundState.indexes[0]] ? `url(${backgroundSequence[backgroundState.indexes[0]]})` : "none" }}
                />
                <div
                    className={`bg-slide ${backgroundState.active === 1 ? "is-active" : ""}`}
                    style={{ backgroundImage: backgroundSequence[backgroundState.indexes[1]] ? `url(${backgroundSequence[backgroundState.indexes[1]]})` : "none" }}
                />
                <div className="bg-overlay" />
            </div>

            <div className="app-shell">
                <section className="glass-panel glass-panel--hero panel-surface">
                    <div className="hero-content">
                        <div className="hero-copy">
                            <p className="eyebrow">Arknights Material Balance</p>
                            <h1>明日方舟素材均衡规划器</h1>
                            <p className="hero-note">
                                <a href="https://ark.yituliu.cn/material/value" target="_blank" rel="noreferrer">权重下载</a>
                                <span> · </span>
                                <a href="https://penguin-stats.io/planner" target="_blank" rel="noreferrer">素材导出</a>
                                <span> · </span>
                                <span>支持 </span>
                                <button type="button" className="hero-note__button" onClick={() => openInventoryExample("maa")}>MAA</button>
                                <span> / </span>
                                <button type="button" className="hero-note__button" onClick={() => openInventoryExample("penguin")}>企鹅物流</button>
                                <span> JSON 自动识别</span>
                                <span> · </span>
                                <a href="https://github.com/LANSGANBS/Arknights" target="_blank" rel="noreferrer">项目地址</a>
                            </p>
                        </div>

                        <div className="hero-controls">
                            <div className="action-grid">
                                <LiquidAction mouseContainerRef={mouseContainerRef} onClick={() => inventoryInputRef.current?.click()}>导入库存</LiquidAction>
                                <LiquidAction mouseContainerRef={mouseContainerRef} onClick={() => weightInputRef.current?.click()}>导入权重</LiquidAction>
                                <LiquidAction mouseContainerRef={mouseContainerRef} className="liquid-button--accent" onClick={exportInventory}>下载库存</LiquidAction>
                                <LiquidAction mouseContainerRef={mouseContainerRef} onClick={() => openConfirmation("reset")}>重置</LiquidAction>
                                <LiquidAction mouseContainerRef={mouseContainerRef} className="liquid-button--primary" onClick={analyze}>计算规划</LiquidAction>
                            </div>
                        </div>
                    </div>
                </section>

                {pendingCopy ? (
                    <div className="confirm-overlay" role="dialog" aria-modal="true">
                        <div className="confirm-panel panel-surface">
                            <div className="confirm-copy">
                                <h3>{pendingCopy.title}</h3>
                                <p>{pendingCopy.description}</p>
                            </div>
                            <div className="confirm-actions">
                                <LiquidAction mouseContainerRef={mouseContainerRef} onClick={closeConfirmation}>取消</LiquidAction>
                                <LiquidAction mouseContainerRef={mouseContainerRef} className="liquid-button--primary" onClick={confirmPendingAction}>{pendingCopy.confirmText}</LiquidAction>
                            </div>
                        </div>
                    </div>
                ) : null}
                {examplePreview ? (
                    <div className="confirm-overlay" role="dialog" aria-modal="true">
                        <div className="confirm-panel panel-surface example-panel">
                            <div className="confirm-copy">
                                <h3>{examplePreview.title}</h3>
                                <p>{examplePreview.description}</p>
                            </div>
                            <div className="example-code-wrap">
                                <div className="example-code-meta">{examplePreview.fileName}</div>
                                <pre className="example-code-block">{examplePreview.content}</pre>
                            </div>
                            <div className="confirm-actions">
                                <LiquidAction mouseContainerRef={mouseContainerRef} onClick={closeInventoryExample}>关闭</LiquidAction>
                            </div>
                        </div>
                    </div>
                ) : null}
                <section className="glass-panel glass-panel--section panel-surface">
                    <div className="section-content">
                        <div className="section-header section-header--results">
                            <div className="section-title-wrap">
                                <div className="result-title-row">
                                    <h2>最缺少的蓝色素材</h2>
                                    <div className="result-links">
                                        <a className="result-link" href="https://ark.yituliu.cn/" target="_blank" rel="noreferrer">掉落推荐关卡</a>
                                    </div>
                                </div>
                            </div>
                            {canExpand ? (
                                <LiquidAction mouseContainerRef={mouseContainerRef} className="liquid-button--secondary liquid-button--toggle" onClick={() => setShowFullRanking((value) => !value)}>
                                    {showFullRanking ? "收起完整排序" : "展开完整排序"}
                                </LiquidAction>
                            ) : null}
                        </div>

                        {visibleShortages.length > 0 ? (
                            <div className="result-grid">
                                {visibleShortages.map((item) => {
                                    const material = materialMap[item.item_id];
                                    const weighted = activeResult?.hasWeights ? item.weighted_equivalent.toFixed(2) : "-";

                                    return (
                                        <article className="result-card" key={item.item_id}>
                                            <span className="result-rank">#{item.rank}</span>
                                            <div className="result-card__head">
                                                <MaterialImage material={material || { name: item.name }} className="result-icon" />
                                                <div>
                                                    <strong>{material?.name || item.name}</strong>
                                                    <span>{item.item_id}</span>
                                                </div>
                                            </div>
                                            <dl className="result-metrics">
                                                <div>
                                                    <dt>等效数量</dt>
                                                    <dd>{item.blue_equivalent.toFixed(2)}</dd>
                                                </div>
                                                <div>
                                                    <dt>加权数量</dt>
                                                    <dd>{weighted}</dd>
                                                </div>
                                            </dl>
                                        </article>
                                    );
                                })}
                            </div>
                        ) : null}
                    </div>
                </section>

                <section className="glass-panel glass-panel--section glass-panel--inventory panel-surface">
                    <div className="section-content">
                        <div className="section-header section-header--inventory">
                            <h2>全部素材</h2>
                            <input
                                className="search-input"
                                value={searchText}
                                onChange={(event) => setSearchText(event.target.value)}
                                placeholder="搜索素材名或 ID"
                            />
                        </div>

                        <div className="inventory-grid">
                            {filteredMaterials.map((material) => (
                                <article className="material-card" key={material.id}>
                                    <span className="material-tier">T{material.tier}</span>
                                    <div className="material-art">
                                        <MaterialImage material={material} className="card-image" />
                                    </div>
                                    <div className="material-meta">
                                        <strong>{material.name}</strong>
                                        <span>{material.id}</span>
                                    </div>
                                    <label className="material-quantity">
                                        <span>数量</span>
                                        <input
                                            type="text"
                                            inputMode="numeric"
                                            pattern="[0-9]*"
                                            value={inventory[material.id] ?? 0}
                                            onFocus={(event) => event.target.select()}
                                            onBlur={(event) => updateQuantity(material.id, event.target.value)}
                                            onChange={(event) => handleQuantityInput(material.id, event.target.value)}
                                        />
                                    </label>
                                </article>
                            ))}
                        </div>
                    </div>
                </section>
            </div>
        </div>
    );
}
