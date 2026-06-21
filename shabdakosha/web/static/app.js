function setupAutocomplete(form) {
  const input = form.querySelector('input[name="q"]');
  const panel = form.querySelector("[data-suggestions]");
  const dictionary = form.querySelector('select[name="dictionary_id"], input[name="dictionary_id"]');
  const clearButton = form.querySelector(".input-clear");
  let controller = null;
  let activeIndex = -1;
  let items = [];

  if (!input || !panel) return;

  if (!panel.id) {
    panel.id = `suggestions-${Math.random().toString(36).slice(2, 9)}`;
  }
  panel.setAttribute("role", "listbox");
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-controls", panel.id);

  function updateClearButton() {
    if (clearButton) clearButton.hidden = input.value.length === 0;
  }

  function hidePanel() {
    panel.hidden = true;
    panel.innerHTML = "";
    activeIndex = -1;
    items = [];
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  function selectItem(index) {
    const item = items[index];
    if (!item) return;
    window.location.href = `/word/${encodeURIComponent(item.word || item.base_word)}`;
  }

  function render(suggestions) {
    items = suggestions;
    activeIndex = -1;
    if (!suggestions.length) {
      hidePanel();
      return;
    }
    panel.innerHTML = suggestions
      .map((item, index) => {
        const dictionaries = item.dictionary_ids.join(", ");
        const display = item.display_headword && item.display_headword !== item.word
          ? ` · source: ${item.display_headword}`
          : "";
        return `
          <button class="suggestion-item" type="button" id="${panel.id}-option-${index}" role="option" aria-selected="false" data-index="${index}">
            <span>
              <strong>${escapeHtml(item.word || item.base_word)}</strong>
              <small>${escapeHtml(dictionaries)} · ${item.entry_count} entries${escapeHtml(display)}</small>
            </span>
          </button>
        `;
      })
      .join("");
    panel.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  async function fetchSuggestions() {
    const q = input.value.trim();
    if (q.length < 1) {
      hidePanel();
      return;
    }
    if (controller) controller.abort();
    controller = new AbortController();
    const params = new URLSearchParams({ q });
    if (dictionary && dictionary.value) params.set("dictionary_id", dictionary.value);
    try {
      const response = await fetch(`/api/suggest?${params.toString()}`, {
        signal: controller.signal,
      });
      if (!response.ok) return;
      const data = await response.json();
      render(data.suggestions || []);
    } catch (error) {
      if (error.name !== "AbortError") hidePanel();
    }
  }

  input.addEventListener("input", updateClearButton);
  input.addEventListener("input", debounce(fetchSuggestions, 120));
  input.addEventListener("focus", fetchSuggestions);
  input.addEventListener("keydown", (event) => {
    if (panel.hidden || !items.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeIndex = Math.min(activeIndex + 1, items.length - 1);
      updateActive(panel, input, activeIndex);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      updateActive(panel, input, activeIndex);
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      selectItem(activeIndex);
    } else if (event.key === "Escape") {
      hidePanel();
    }
  });
  panel.addEventListener("click", (event) => {
    const button = event.target.closest("[data-index]");
    if (!button) return;
    selectItem(Number(button.dataset.index));
  });
  document.addEventListener("click", (event) => {
    if (!form.contains(event.target)) hidePanel();
  });

  if (clearButton) {
    clearButton.addEventListener("click", () => {
      input.value = "";
      updateClearButton();
      hidePanel();
      input.focus();
    });
  }

  updateClearButton();
}

function updateActive(panel, input, activeIndex) {
  let activeId = "";
  panel.querySelectorAll("[data-index]").forEach((button, index) => {
    const isActive = index === activeIndex;
    button.dataset.active = isActive ? "true" : "false";
    button.setAttribute("aria-selected", isActive ? "true" : "false");
    if (isActive) activeId = button.id;
  });
  if (activeId) {
    input.setAttribute("aria-activedescendant", activeId);
  } else {
    input.removeAttribute("aria-activedescendant");
  }
}

function debounce(callback, wait) {
  let timeout = null;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => callback(...args), wait);
  };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.querySelectorAll("[data-autocomplete]").forEach(setupAutocomplete);
