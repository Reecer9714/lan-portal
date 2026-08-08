const dialog = document.querySelector("#service-dialog");
const form = document.querySelector("#service-form");
const addButton = document.querySelector("#add-service");
const editModeButton = document.querySelector("#edit-mode");
const cancelButton = document.querySelector("#cancel-service");
const closeButton = document.querySelector("#close-service");
const errorBox = document.querySelector("#form-error");
const dialogTitle = document.querySelector("#service-dialog-title");
const submitButton = document.querySelector("#submit-service");
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
const priorityIconRanges = [
    { name: "Objects", keywords: "tool lock key computer disk folder media service", start: 0x1f4bb, end: 0x1f4c2 },
    { name: "Objects", keywords: "chart mail package notebook service", start: 0x1f4c3, end: 0x1f4e6 },
    { name: "Objects", keywords: "satellite antenna signal media service", start: 0x1f4e1, end: 0x1f4fa },
    { name: "Objects", keywords: "lock key tool wrench service", start: 0x1f510, end: 0x1f527 },
    { name: "Objects", keywords: "network computer printer disk server", start: 0x1f5a5, end: 0x1f5c4 },
    { name: "Supplemental Symbols", keywords: "tools toolbox compass service", start: 0x1f9ed, end: 0x1f9f0 },
    { name: "Supplemental Symbols", keywords: "shield service security", start: 0x1f6e1, end: 0x1f6e1 },
    { name: "Transport and Map", keywords: "rocket satellite service", start: 0x1f680, end: 0x1f6f0 },
    { name: "Miscellaneous Symbols", keywords: "weather music game tool gear star phone warning service", start: 0x2600, end: 0x26a1 },
    { name: "Dingbats", keywords: "check mark cross arrow star decorative office", start: 0x2700, end: 0x2728 },
    { name: "Geometric Shapes", keywords: "shape circle square triangle diamond symbol", start: 0x25a0, end: 0x25c9 },
    { name: "Arrows", keywords: "arrow direction navigation pointer", start: 0x2190, end: 0x21aa }
];
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
let editMode = false;
let editingPath = null;
let services = [];

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
    const seenCodePoints = new Set();

    [...priorityIconRanges, ...iconRanges].forEach((range) => {
        for (let codePoint = range.start; codePoint <= range.end; codePoint += 1) {
            if (seenCodePoints.has(codePoint)) continue;
            seenCodePoints.add(codePoint);

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

function resetDialog() {
    form.reset();
    pathEdited = false;
    editingPath = null;
    dialogTitle.textContent = "Add Service";
    submitButton.textContent = "Add Service";
    updateIconPreview();
    clearError();
}

function closeDialog() {
    dialog.close();
    resetDialog();
}

function openAddDialog() {
    resetDialog();
    dialog.showModal();
    nameInput.focus();
}

function setEditMode(enabled) {
    editMode = enabled;
    document.body.classList.toggle("is-editing-services", editMode);
    editModeButton.setAttribute("aria-pressed", String(editMode));
    editModeButton.textContent = editMode ? "Done Editing" : "Edit Mode";
}

async function loadServices() {
    const response = await fetch("/api/services");
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.error || "Unable to load services.");
    }
    services = result.services || [];
}

function getServiceFromElement(element) {
    if (!element || !element.dataset.service) return null;
    try {
        return JSON.parse(element.dataset.service);
    } catch (error) {
        return null;
    }
}

function getPathFromServiceCard(serviceCard) {
    if (!serviceCard) return "";
    if (serviceCard.dataset.servicePath) return serviceCard.dataset.servicePath;
    try {
        return new URL(serviceCard.href, window.location.href).pathname.replace(/^\/+|\/+$/g, "");
    } catch (error) {
        return serviceCard.getAttribute("href").replace(/^\/+|\/+$/g, "");
    }
}

function openEditDialog(service) {
    resetDialog();
    editingPath = service.path;
    pathEdited = true;
    dialogTitle.textContent = "Edit Service";
    submitButton.textContent = "Save Changes";
    form.elements.name.value = service.name || "";
    form.elements.path.value = service.path || "";
    form.elements.host.value = service.host || "";
    form.elements.port.value = service.port || "";
    form.elements.description.value = service.description || "";
    form.elements.icon.value = service.icon || "";
    form.elements.scheme.value = service.scheme || "http";
    updateIconPreview();
    dialog.showModal();
    nameInput.focus();
}

async function editService(path, shell) {
    try {
        clearError();
        let service = getServiceFromElement(shell);
        if (!service) {
            if (!services.length) await loadServices();
            service = services.find((item) => String(item.path).replace(/^\/+|\/+$/g, "") === path);
        }
        if (!service) throw new Error("Service not found.");
        openEditDialog(service);
    } catch (error) {
        if (!dialog.open) {
            resetDialog();
            dialogTitle.textContent = "Edit Service";
            submitButton.textContent = "Save Changes";
            dialog.showModal();
        }
        showError(error.message);
    }
}

addButton.addEventListener("click", openAddDialog);
editModeButton.addEventListener("click", () => setEditMode(!editMode));

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

document.addEventListener("click", (event) => {
    const editButton = event.target.closest(".service-edit-button");
    if (editButton) {
        editService(editButton.dataset.servicePath, editButton.closest(".service-card-shell"));
        return;
    }

    const serviceCard = event.target.closest(".service-card");
    if (serviceCard && editMode) {
        event.preventDefault();
        const shell = serviceCard.closest(".service-card-shell");
        const shellEditButton = shell && shell.querySelector(".service-edit-button");
        const servicePath = shellEditButton ? shellEditButton.dataset.servicePath : getPathFromServiceCard(serviceCard);
        if (servicePath) editService(servicePath, shell || serviceCard);
    }
});

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
    if (editingPath) data.originalPath = editingPath;

    if (!data.host.trim()) delete data.host;
    if (!data.description.trim()) delete data.description;
    if (!data.icon.trim()) delete data.icon;

    try {
        const response = await fetch("/api/services", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });

        const responseText = await response.text();
        let result = {};
        try {
            result = responseText ? JSON.parse(responseText) : {};
        } catch (error) {
            throw new Error(response.ok ? "Server returned an invalid response." : "Server returned an HTML error page.");
        }

        if (!response.ok) {
            throw new Error(result.error || "Unable to add service.");
        }

        window.location.reload();
    } catch (error) {
        showError(error.message);
    }
});
