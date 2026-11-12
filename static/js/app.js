function setupSpecialtyGroups() {
  const toggles = document.querySelectorAll("[data-specialty-toggle]");

  toggles.forEach((toggle) => {
    const group = document.querySelector(
      `[data-services-group="${toggle.value}"]`
    );
    if (!group) return;

    const sync = () => {
      const isVisible = toggle.checked;
      group.classList.toggle("hidden", !isVisible);

      if (!isVisible) {
        group.querySelectorAll('input[name="services"]').forEach((box) => {
          if (box.checked) {
            box.checked = false;
            box.dispatchEvent(new Event("change", { bubbles: true }));
          }
        });
      }
    };

    toggle.addEventListener("change", sync);
    sync();
  });

  document.querySelectorAll("[data-select-all]").forEach((button) => {
    const group = document.querySelector(
      `[data-services-group="${button.dataset.selectAll}"]`
    );
    if (!group) return;

    const boxes = Array.from(group.querySelectorAll('input[name="services"]'));

    const updateLabel = () => {
      const allChecked = boxes.length > 0 && boxes.every((box) => box.checked);
      button.textContent = allChecked ? "Quitar todos" : "Seleccionar todos";
    };

    boxes.forEach((box) => box.addEventListener("change", updateLabel));

    button.addEventListener("click", (event) => {
      event.preventDefault();
      const shouldCheck = boxes.some((box) => !box.checked);
      boxes.forEach((box) => {
        box.checked = shouldCheck;
      });
      updateLabel();
    });

    updateLabel();
  });
}

function setupScheduleFormset() {
  const container = document.querySelector("[data-schedule-formset]");
  if (!container) return;

  const rows = container.querySelector("[data-schedule-rows]");
  const template = container.querySelector("#schedule-empty-form");
  const totalForms = container.querySelector('input[name$="-TOTAL_FORMS"]');
  const addButton = container.querySelector("[data-add-schedule-row]");
  if (!rows || !template || !totalForms || !addButton) return;

  addButton.addEventListener("click", () => {
    const index = Number.parseInt(totalForms.value, 10);
    const html = template.innerHTML
      .split("__prefix__")
      .join(String(index));
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html.trim();
    const row = wrapper.firstElementChild;
    if (!row) return;

    rows.appendChild(row);
    totalForms.value = String(index + 1);

    const firstField = row.querySelector("select, input:not([type='hidden'])");
    if (firstField) firstField.focus();
  });

  rows.addEventListener("change", (event) => {
    const checkbox = event.target.closest('input[type="checkbox"][name$="-DELETE"]');
    if (!checkbox) return;
    const row = checkbox.closest("[data-schedule-row]");
    if (row) row.classList.toggle("opacity-50", checkbox.checked);
  });
}

function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
  return Promise.resolve();
}

function setupCopyButtons() {
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-copy-text]");
    if (!button) return;

    const text = button.dataset.copyText || "";
    if (!button.dataset.originalHtml) {
      button.dataset.originalHtml = button.innerHTML;
    }
    try {
      await copyText(text);
      button.textContent = "Copiado ✓";
    } catch {
      button.textContent = "No se pudo copiar";
    }
    window.setTimeout(() => {
      button.innerHTML = button.dataset.originalHtml;
    }, 1800);
  });
}

function setupConfirmationForms() {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
}

function setupAppMenu() {
  const menu = document.querySelector("[data-app-menu]");
  if (!menu) return;

  const summary = menu.querySelector("summary");
  const desktop = window.matchMedia("(min-width: 768px)");

  document.addEventListener("click", (event) => {
    if (!menu.open || menu.contains(event.target)) return;
    menu.open = false;
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !menu.open) return;
    menu.open = false;
    summary?.focus();
  });

  desktop.addEventListener("change", (event) => {
    if (event.matches) menu.open = false;
  });
}

function setupServiceWorker() {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupSpecialtyGroups();
  setupScheduleFormset();
  setupCopyButtons();
  setupConfirmationForms();
  setupAppMenu();
  setupServiceWorker();
});
