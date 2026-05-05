const materialImageModules = import.meta.glob("../../assets/materials/*.{png,gif,jpg,jpeg,avif,webp}", {
    eager: true,
    import: "default",
});

const backgroundImageModules = import.meta.glob("../../assets/backgrounds/*.{png,gif,jpg,jpeg,avif,webp}", {
    eager: true,
    import: "default",
});

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

export const BACKGROUND_IMAGES = backgroundEntries.map((entry) => entry.url);
