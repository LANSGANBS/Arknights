import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import LiquidGlass from "liquid-glass-react";

const EMPTY_DOCUMENT = {
    "@type": "@penguin-statistics/planner/config",
    items: [],
    options: {},
    excludes: [],
};

const BUTTON_GLASS = {
    mode: "prominent",
    blurAmount: 0.075,
    saturation: 128,
    displacementScale: 88,
    aberrationIntensity: 2.1,
    elasticity: 0,
    cornerRadius: 22,
    padding: "0px",
    overLight: false,
};

const CONFIRMATION_COPY = {
    import: {
        title: "确认导入",
        description: "这会重新读取当前配置里的库存文件，并覆盖页面上已经修改但尚未导出的数量。",
        confirmText: "确认导入",
    },
    export: {
        title: "确认导出",
        description: "这会把当前页面上的库存数量写回导出文件。",
        confirmText: "确认导出",
    },
    reset: {
        title: "确认重置",
        description: "这会把当前页面上的数量恢复为最近一次导入时的原始值。",
        confirmText: "确认重置",
    },
};

async function requestJson(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || "请求失败");
    }
    return payload;
}

function MaterialImage({ material, className }) {
    if (material?.imageUrl) {
        return <img className={className} src={material.imageUrl} alt={material.name} />;
    }
    return <span className={`${className} placeholder`}>无图</span>;
}

function LiquidAction({ className = "", onClick, children, mouseContainerRef }) {
    return (
        <div className={`liquid-button-shell ${className}`.trim()}>
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

export default function App() {
    const mouseContainerRef = useRef(null);
    const [originalDocument, setOriginalDocument] = useState(EMPTY_DOCUMENT);
    const [inventory, setInventory] = useState({});
    const [materials, setMaterials] = useState([]);
    const [result, setResult] = useState(null);
    const [fullResult, setFullResult] = useState(null);
    const [showFullRanking, setShowFullRanking] = useState(false);
    const [useCustomWeights, setUseCustomWeights] = useState(false);
    const [outputPath, setOutputPath] = useState("data/export.json");
    const [backgroundImages, setBackgroundImages] = useState([]);
    const [backgroundState, setBackgroundState] = useState({ active: 0, indexes: [0, 0] });
    const [searchText, setSearchText] = useState("");
    const [statusText, setStatusText] = useState("");
    const [pendingAction, setPendingAction] = useState(null);
    const deferredSearchText = useDeferredValue(searchText);

    const materialMap = useMemo(
        () => Object.fromEntries(materials.map((material) => [material.id, material])),
        [materials]
    );

    const filteredMaterials = useMemo(() => {
        const keyword = deferredSearchText.trim().toLowerCase();
        if (!keyword) {
            return materials;
        }
        return materials.filter(
            (material) =>
                material.name.toLowerCase().includes(keyword) || material.id.toLowerCase().includes(keyword)
        );
    }, [materials, deferredSearchText]);

    const canExpand = (fullResult?.shortages?.length || 0) > (result?.shortages?.length || 0);
    const visibleShortages = showFullRanking && fullResult ? fullResult.shortages : result?.shortages || [];

    useEffect(() => {
        const load = async () => {
            try {
                setStatusText("");
                const payload = await requestJson("/api/bootstrap");
                setOriginalDocument(payload.document || EMPTY_DOCUMENT);
                setInventory(payload.inventory || {});
                setMaterials(payload.materials || []);
                setResult(payload.result || null);
                setFullResult(payload.fullResult || payload.result || null);
                setUseCustomWeights(Boolean(payload.useCustomWeights));
                setOutputPath(payload.outputPath || "data/export.json");
                setBackgroundImages(payload.backgroundImages || []);
                setShowFullRanking(false);
            } catch (error) {
                setStatusText(error.message || "初始化失败");
            }
        };

        load();
    }, []);

    useEffect(() => {
        setBackgroundState({ active: 0, indexes: [0, 0] });
        if (backgroundImages.length <= 1) {
            return undefined;
        }

        const timer = window.setInterval(() => {
            setBackgroundState((prev) => {
                const nextActive = prev.active === 0 ? 1 : 0;
                const currentIndex = prev.indexes[prev.active];
                const nextIndex = (currentIndex + 1) % backgroundImages.length;
                const nextIndexes = [...prev.indexes];
                nextIndexes[nextActive] = nextIndex;
                return { active: nextActive, indexes: nextIndexes };
            });
        }, 16000);

        return () => window.clearInterval(timer);
    }, [backgroundImages]);

    const analyze = async () => {
        try {
            setStatusText("");
            const payload = await requestJson("/api/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ inventory, useCustomWeights }),
            });
            setResult(payload.result || null);
            setFullResult(payload.fullResult || payload.result || null);
            setShowFullRanking(false);
        } catch (error) {
            setStatusText(error.message || "分析失败");
        }
    };

    const reloadInventory = async () => {
        try {
            setStatusText("");
            const payload = await requestJson("/api/bootstrap");
            setOriginalDocument(payload.document || EMPTY_DOCUMENT);
            setInventory(payload.inventory || {});
            setMaterials(payload.materials || []);
            setResult(payload.result || null);
            setFullResult(payload.fullResult || payload.result || null);
            setUseCustomWeights(Boolean(payload.useCustomWeights));
            setOutputPath(payload.outputPath || "data/export.json");
            setBackgroundImages(payload.backgroundImages || []);
            setShowFullRanking(false);
        } catch (error) {
            setStatusText(error.message || "导入失败");
        }
    };

    const exportInventory = async () => {
        try {
            setStatusText("");
            await requestJson("/api/export", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ inventory, templateDocument: originalDocument }),
            });
        } catch (error) {
            setStatusText(error.message || "导出失败");
        }
    };

    const resetInventory = () => {
        const nextInventory = {};
        for (const entry of originalDocument?.items || []) {
            nextInventory[entry.id] = entry.have;
        }
        setInventory(nextInventory);
        setStatusText("");
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

    const confirmPendingAction = async () => {
        if (pendingAction === "import") {
            await reloadInventory();
        } else if (pendingAction === "export") {
            await exportInventory();
        } else if (pendingAction === "reset") {
            resetInventory();
        }
        setPendingAction(null);
    };

    const pendingCopy = pendingAction ? CONFIRMATION_COPY[pendingAction] : null;

    return (
        <div className="page-shell" ref={mouseContainerRef}>
            <div className="background-stage" aria-hidden="true">
                <div
                    className={`bg-slide ${backgroundState.active === 0 ? "is-active" : ""}`}
                    style={{ backgroundImage: backgroundImages[backgroundState.indexes[0]] ? `url(${backgroundImages[backgroundState.indexes[0]]})` : "none" }}
                />
                <div
                    className={`bg-slide ${backgroundState.active === 1 ? "is-active" : ""}`}
                    style={{ backgroundImage: backgroundImages[backgroundState.indexes[1]] ? `url(${backgroundImages[backgroundState.indexes[1]]})` : "none" }}
                />
                <div className="bg-overlay" />
            </div>

            <div className="app-shell">
                <section className="glass-panel glass-panel--hero panel-surface">
                    <div className="hero-content">
                        <div className="hero-copy">
                            <p className="eyebrow">Arknights Material Balance</p>
                            <h1>明日方舟素材均衡规划器</h1>
                        </div>

                        <div className="hero-controls">
                            <label className="weight-toggle">
                                <input type="checkbox" checked={useCustomWeights} onChange={(event) => setUseCustomWeights(event.target.checked)} />
                                <span>启用权重模式</span>
                            </label>

                            <div className="action-grid">
                                <LiquidAction mouseContainerRef={mouseContainerRef} onClick={() => openConfirmation("import")}>导入</LiquidAction>
                                <LiquidAction mouseContainerRef={mouseContainerRef} className="liquid-button--accent" onClick={() => openConfirmation("export")}>导出</LiquidAction>
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

                {statusText ? <div className="status-banner">{statusText}</div> : null}

                <section className="glass-panel glass-panel--section panel-surface">
                    <div className="section-content">
                        <div className="section-header section-header--results">
                            <div className="section-title-wrap">
                                <div className="result-title-row">
                                    <h2>最缺少的蓝色素材</h2>
                                    <div className="result-links">
                                        <a className="result-link" href="https://ark.yituliu.cn/" target="_blank" rel="noreferrer">掉落推荐关卡</a>
                                        <a className="result-link" href="https://ark.yituliu.cn/material/value" target="_blank" rel="noreferrer">权重下载</a>
                                    </div>
                                </div>
                            </div>
                            {canExpand ? (
                                <LiquidAction mouseContainerRef={mouseContainerRef} className="liquid-button--secondary liquid-button--toggle" onClick={() => setShowFullRanking((value) => !value)}>
                                    {showFullRanking ? "收起完整排序" : "展开完整排序"}
                                </LiquidAction>
                            ) : null}
                        </div>

                        <div className="result-grid">
                            {visibleShortages.map((item) => {
                                const material = materialMap[item.item_id];
                                const weighted = (showFullRanking && fullResult ? fullResult.weightMode : result?.weightMode) === "custom"
                                    ? item.weighted_equivalent.toFixed(2)
                                    : "-";

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
                                                <dt>蓝材等效</dt>
                                                <dd>{item.blue_equivalent.toFixed(2)}</dd>
                                            </div>
                                            <div>
                                                <dt>加权后</dt>
                                                <dd>{weighted}</dd>
                                            </div>
                                        </dl>
                                    </article>
                                );
                            })}
                        </div>
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
