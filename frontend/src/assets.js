const materialImageModules = import.meta.glob("../../assets/materials/*.{png,gif,jpg,jpeg,avif,webp}", {
    eager: true,
    import: "default",
});

const backgroundImageModules = import.meta.glob("../../assets/backgrounds/*.{png,gif,jpg,jpeg,avif,webp}", {
    eager: true,
    import: "default",
});

const DEFERRED_BACKGROUND_GROUP = new Set([
    "470f3f0f95c6af4f791d28d9aed48079161775300.webp",
    "53e2cb5c5a243add4bfb67c54d1ecb68161775300.webp",
    "6903395f9b2c36474bd762b63d4ccf75161775300.webp",
]);

function fileNameFromPath(path) {
    return path.split("/").pop() || path;
}

function basenameWithoutExtension(path) {
    return fileNameFromPath(path).replace(/\.[^.]+$/, "");
}

export const MATERIAL_IMAGE_MAP = Object.fromEntries(
    Object.entries(materialImageModules).map(([path, url]) => [basenameWithoutExtension(path), url])
);

const backgroundEntries = Object.entries(backgroundImageModules).map(([path, url]) => ({
    name: fileNameFromPath(path),
    url,
}));

export const BACKGROUND_IMAGES = [
    ...backgroundEntries.filter((entry) => !DEFERRED_BACKGROUND_GROUP.has(entry.name)).map((entry) => entry.url),
    ...backgroundEntries.filter((entry) => DEFERRED_BACKGROUND_GROUP.has(entry.name)).map((entry) => entry.url),
];
