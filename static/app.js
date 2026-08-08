const dialog = document.querySelector("#service-dialog");
const form = document.querySelector("#service-form");
const addButton = document.querySelector("#add-service");
const cancelButton = document.querySelector("#cancel-service");
const closeButton = document.querySelector("#close-service");
const errorBox = document.querySelector("#form-error");

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
    clearError();
}

addButton.addEventListener("click", () => {
    clearError();
    dialog.showModal();
    form.elements.name.focus();
});

cancelButton.addEventListener("click", closeDialog);
closeButton.addEventListener("click", closeDialog);

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
