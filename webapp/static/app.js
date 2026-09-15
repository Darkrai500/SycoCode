"use strict";
const forms = [...document.querySelectorAll(".annotation-form")];
const states = new Map();
function values(form) { return {label: form.querySelector("input[name=label]:checked")?.value, note: form.querySelector("textarea").value}; }
function updateCase() {
  const complete = forms.every(f => f.dataset.saved === "true" && !states.get(f).dirty && !states.get(f).saving);
  const line = document.querySelector("#case-status");
  if (line) line.textContent = complete ? "Todas las respuestas de este caso están guardadas." : "Etiqueta las respuestas señaladas para completar el caso.";
}
async function save(form) {
  const state = states.get(form);
  clearTimeout(state.timer);
  const value = values(form);
  if (!value.label || state.saving) return;
  state.saving = true;
  const snapshot = JSON.stringify(value);
  const status = form.querySelector(".save-state");
  const retry = form.querySelector(".retry");
  status.textContent = "Guardando…";
  status.classList.remove("failed");
  retry.hidden = true;
  updateCase();
  const controller = new AbortController();
  let success = false;
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(form.dataset.url, {method: "POST", credentials: "same-origin", signal: controller.signal,
      headers: {"Content-Type": "application/json", "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value},
      body: JSON.stringify({...value, version: Number(form.dataset.version)})});
    const isJson = response.headers.get("content-type")?.includes("application/json");
    if (response.redirected || !isJson) throw new Error("La sesión puede haber caducado. Accede de nuevo en otra pestaña y reintenta; tu elección sigue aquí.");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "No se pudo guardar. Reintenta sin cerrar esta página.");
    form.dataset.version = result.version;
    form.dataset.saved = "true";
    state.dirty = JSON.stringify(values(form)) !== snapshot;
    status.textContent = "Guardado";
    success = true;
  } catch (error) {
    state.dirty = true;
    status.textContent = error.name === "AbortError" || error instanceof TypeError
      ? "No se ha confirmado el guardado. Comprueba la conexión y pulsa Reintentar." : error.message;
    status.classList.add("failed");
    retry.hidden = false;
  } finally {
    clearTimeout(timeout);
    state.saving = false;
    updateCase();
    if (success && state.dirty) queueMicrotask(() => save(form));
  }
}
forms.forEach(form => {
  states.set(form, {dirty: false, saving: false, timer: null});
  form.addEventListener("submit", event => event.preventDefault());
  form.querySelectorAll("input[name=label]").forEach(input => input.addEventListener("change", () => {
    states.get(form).dirty = true; save(form);
  }));
  form.querySelector("textarea").addEventListener("input", () => {
    const state = states.get(form); state.dirty = true;
    clearTimeout(state.timer);
    form.querySelector(".save-state").textContent = values(form).label ? "Cambios sin guardar…" : "Selecciona una etiqueta para guardar también la nota.";
    state.timer = setTimeout(() => save(form), 700);
    updateCase();
  });
  form.querySelector(".retry").addEventListener("click", () => save(form));
});
window.addEventListener("beforeunload", event => {
  if ([...states.values()].some(state => state.dirty || state.saving)) { event.preventDefault(); event.returnValue = ""; }
});
document.querySelector("#next-case")?.addEventListener("click", event => {
  if ([...states.values()].some(state => state.dirty || state.saving)) {
    event.preventDefault();
    document.querySelector("#case-status").textContent = "Hay cambios pendientes. Espera al guardado o pulsa Reintentar antes de continuar.";
  } else if (forms.some(form => form.dataset.saved !== "true")) {
    event.preventDefault();
    const pending = forms.find(form => form.dataset.saved !== "true");
    pending.scrollIntoView({block: "center", behavior: "auto"});
    pending.querySelector("input[name=label]").focus();
    document.querySelector("#case-status").textContent = "Queda una respuesta sin etiquetar. Puedes dejar el caso para después desde Mis casos.";
  }
});
