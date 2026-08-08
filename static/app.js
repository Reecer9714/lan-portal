const dialog = document.querySelector("#service-dialog");
const form = document.querySelector("#service-form");
const addButton = document.querySelector("#add-service");
const cancelButton = document.querySelector("#cancel-service");
const closeButton = document.querySelector("#close-service");
const errorBox = document.querySelector("#form-error");
const nameInput = form.elements.name;
const pathInput = form.elements.path;
const iconInput = document.querySelector("#service-icon-input");
const iconPreview = document.querySelector("#icon-preview");
const iconGrid = document.querySelector("#unicode-icon-grid");
const iconSearch = document.querySelector("#unicode-icon-search");
const iconPagePrev = document.querySelector("#icon-page-prev");
const iconPageNext = document.querySelector("#icon-page-next");
const iconPageStatus = document.querySelector("#icon-page-status");
const iconPageSize = 72;
const defaultIcon = String.fromCodePoint(0x25c8);
const iconRanges = [
    { name: "Geometric Shapes", keywords: "shape circle square triangle diamond symbol", start: 0x25a0, end: 0x25ff },
    { name: "Miscellaneous Symbols", keywords: "weather music game tool gear star phone warning service", start: 0x2600, end: 0x26ff },
    { name: "Dingbats", keywords: "check mark cross arrow star decorative office", start: 0x2700, end: 0x27bf },
    { name: "Arrows", keywords: "arrow direction navigation pointer", start: 0x2190, end: 0x21ff },
    { name: "Technical", keywords: "keyboard command house watch technical", start: 0x2300, end: 0x23ff },
    { name: "Transport and Map", keywords: "car train ship airplane map place", start: 0x1f680, end: 0x1f6ff },
    { name: "Objects", keywords: "tool lock key computer disk folder media service", start: 0x1f300, end: 0x1f5ff },
    { name: "Supplemental Symbols", keywords: "tools shield wizard service symbol", start: 0x1f900, end: 0x1f9ff }
];
const unicodeIcons = buildIconSet();
let iconPage = 0;
let pathEdited = false;

function slugify(value) {
    return value
        .normalize("NFKD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
}

function updatePathFromName() {
    if (!pathEdited) {
        pathInput.value = slugify(nameInput.value);
    }
}

function updateIconPreview() {
    iconPreview.textContent = iconInput.value.trim() || defaultIcon;
}

function selectIcon(icon) {
    iconInput.value = icon;
    updateIconPreview();
    iconInput.focus();
}

function buildIconSet() {
    const icons = [];
    iconRanges.forEach((range) => {
        for (let codePoint = range.start; codePoint <= range.end; codePoint += 1) {
            const icon = String.fromCodePoint(codePoint);
            icons.push({
                icon,
                codePoint,
                range: range.name,
                searchText: `${range.name} ${range.keywords} ${icon} ${codePoint.toString(16)} u+${codePoint.toString(16)}`.toLowerCase()
            });
        }
    });
    return icons;
}

function getFilteredIcons() {
    const query = iconSearch.value.trim().toLowerCase();
    if (!query) return unicodeIcons;
    const normalizedQuery = query.replace(/^u\+/, "");
    return unicodeIcons.filter((item) => (
        item.searchText.includes(query)
        || item.searchText.includes(normalizedQuery)
        || item.icon === query
    ));
}

function renderIconPicker() {
    const filteredIcons = getFilteredIcons();
    const pageCount = Math.max(1, Math.ceil(filteredIcons.length / iconPageSize));
    iconPage = Math.min(iconPage, pageCount - 1);
    const pageIcons = filteredIcons.slice(iconPage * iconPageSize, (iconPage + 1) * iconPageSize);

    iconGrid.replaceChildren();
    pageIcons.forEach((item) => {
        const button = document.createElement("button");
        button.className = "unicode-icon-option";
        button.type = "button";
        button.textContent = item.icon;
        button.title = `${item.range} U+${item.codePoint.toString(16).toUpperCase()}`;
        button.setAttribute("aria-label", `Use ${item.icon} as the service icon`);
        button.addEventListener("click", () => selectIcon(item.icon));
        iconGrid.append(button);
    });

    iconPageStatus.textContent = filteredIcons.length
        ? `Page ${iconPage + 1} of ${pageCount}`
        : "No icons";
    iconPagePrev.disabled = iconPage === 0;
    iconPageNext.disabled = iconPage >= pageCount - 1 || filteredIcons.length === 0;
}

function changeIconPage(direction) {
    iconPage += direction;
    renderIconPicker();
}

function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
}

function clearError() {
    errorBox.textContent = "";
    errorBox.hidden = true;
}

function closeDialog() {
    dialog.close();
    form.reset();
    pathEdited = false;
    updateIconPreview();
    clearError();
}

addButton.addEventListener("click", () => {
    clearError();
    dialog.showModal();
    nameInput.focus();
});

cancelButton.addEventListener("click", closeDialog);
closeButton.addEventListener("click", closeDialog);
nameInput.addEventListener("input", updatePathFromName);
pathInput.addEventListener("input", () => {
    pathEdited = true;
    pathInput.value = slugify(pathInput.value);
});
iconInput.addEventListener("input", updateIconPreview);
iconSearch.addEventListener("input", () => {
    iconPage = 0;
    renderIconPicker();
});
iconPagePrev.addEventListener("click", () => changeIconPage(-1));
iconPageNext.addEventListener("click", () => changeIconPage(1));
renderIconPicker();
updateIconPreview();

dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
        closeDialog();
    }
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();

    const data = Object.fromEntries(new FormData(form).entries());
    data.port = Number(data.port);
    data.path = data.path.trim().replace(/^\/+|\/+$/g, "");

    if (!data.host.trim()) delete data.host;
    if (!data.description.trim()) delete data.description;
    if (!data.icon.trim()) delete data.icon;

    try {
        const response = await fetch("/api/services", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Unable to add service.");
        }

        window.location.reload();
    } catch (error) {
        showError(error.message);
    }
});
