function setupAutocomplete(form) {
  const input = form.querySelector('input[name="q"]');
  const panel = form.querySelector("[data-suggestions]");
  const dictionary = form.querySelector('select[name="dictionary_id"], input[name="dictionary_id"]');
  let controller = null;
  let activeIndex = -1;
  let items = [];

  if (!input || !panel) return;

  function hidePanel() {
    panel.hidden = true;
    panel.innerHTML = "";
    activeIndex = -1;
    items = [];
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
          <button class="suggestion-item" type="button" data-index="${index}">
            <span>
              <strong>${escapeHtml(item.word || item.base_word)}</strong>
              <small>${escapeHtml(dictionaries)} · ${item.entry_count} entries${escapeHtml(display)}</small>
            </span>
          </button>
        `;
      })
      .join("");
    panel.hidden = false;
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

  input.addEventListener("input", debounce(fetchSuggestions, 120));
  input.addEventListener("focus", fetchSuggestions);
  input.addEventListener("keydown", (event) => {
    if (panel.hidden || !items.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeIndex = Math.min(activeIndex + 1, items.length - 1);
      updateActive(panel, activeIndex);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      updateActive(panel, activeIndex);
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
}

function updateActive(panel, activeIndex) {
  panel.querySelectorAll("[data-index]").forEach((button, index) => {
    button.dataset.active = index === activeIndex ? "true" : "false";
  });
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
