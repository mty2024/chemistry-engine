/* chemistry-engine — small, dependency-free site behaviour */
(() => {
  "use strict";

  const THEME_KEY = "chemistry-engine-theme";
  const root = document.documentElement;

  function applyTheme(theme) {
    root.dataset.theme = theme;
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const isDark = theme === "dark";
      button.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
      button.setAttribute("aria-pressed", String(isDark));
      button.title = isDark ? "Switch to light theme" : "Switch to dark theme";
    });
  }

  function initTheme() {
    let stored = null;
    try {
      stored = window.localStorage.getItem(THEME_KEY);
    } catch (error) {
      stored = null;
    }
    const queryTheme = new URLSearchParams(window.location.search).get("theme");
    const preferred =
      queryTheme === "dark" || queryTheme === "light"
        ? queryTheme
        : stored || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    applyTheme(preferred);
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const next = root.dataset.theme === "dark" ? "light" : "dark";
        try {
          window.localStorage.setItem(THEME_KEY, next);
        } catch (error) {
          /* storage may be unavailable */
        }
        applyTheme(next);
      });
    });
  }

  function initNavigation() {
    const toggle = document.querySelector("[data-menu-toggle]");
    const nav = document.querySelector("[data-nav]");
    if (!toggle || !nav) return;
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    nav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        nav.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (error) {
        /* fall through to the legacy path */
      }
    }
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (error) {
      ok = false;
    }
    textarea.remove();
    return ok;
  }

  function flash(button, ok) {
    const previous = button.textContent;
    button.textContent = ok ? "Copied!" : "Press Ctrl+C";
    window.setTimeout(() => {
      button.textContent = previous;
    }, 1500);
  }

  function initCopyButtons() {
    document.querySelectorAll("pre").forEach((pre) => {
      if (pre.dataset.noCopy !== undefined) return;
      const code = pre.querySelector("code");
      const text = (code || pre).textContent.trim();
      const button = document.createElement("button");
      button.type = "button";
      button.className = "copy";
      button.textContent = "Copy";
      button.setAttribute("aria-label", "Copy code to clipboard");
      button.addEventListener("click", async () => {
        flash(button, await copyText(text));
      });
      pre.appendChild(button);
    });

    document.querySelectorAll("[data-copy-target]").forEach((button) => {
      button.addEventListener("click", async () => {
        const target = document.querySelector(button.dataset.copyTarget);
        if (!target) return;
        flash(button, await copyText(target.textContent.trim()));
      });
    });
  }

  function formatMass(value) {
    if (!Number.isFinite(value)) return String(value);
    return value.toLocaleString("en-US", { maximumFractionDigits: 5 });
  }

  function elementNode(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  async function initElementExplorer() {
    const grid = document.querySelector("[data-elements]");
    if (!grid) return;
    const detail = document.querySelector("[data-element-detail]");
    const search = document.querySelector("[data-element-search]");
    const count = document.querySelector("[data-element-count]");
    let elements = [];
    let selected = "Fe";

    try {
      const response = await fetch("assets/elements.json", { cache: "no-cache" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      elements = payload.elements;
    } catch (error) {
      grid.replaceChildren(
        elementNode("p", "muted", "Element data is unavailable. Run `python tools/build_site.py` first.")
      );
      return;
    }

    const render = (list) => {
      grid.replaceChildren();
      if (!list.length) {
        grid.append(elementNode("p", "muted", "No elements match that search."));
        return;
      }
      list.forEach((element) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "element-card";
        card.dataset.symbol = element.symbol;
        card.setAttribute("aria-pressed", String(element.symbol === selected));
        card.setAttribute(
          "aria-label",
          `${element.name}, symbol ${element.symbol}, atomic number ${element.z}`
        );
        card.append(
          elementNode("span", "sym", element.symbol),
          elementNode("span", "z", `Z=${element.z}`),
          elementNode("span", "mass", formatMass(element.mass))
        );
        card.addEventListener("click", () => select(element));
        grid.append(card);
      });
    };

    const select = (element) => {
      selected = element.symbol;
      grid.querySelectorAll(".element-card").forEach((card) => {
        card.setAttribute("aria-pressed", String(card.dataset.symbol === element.symbol));
      });
      if (!detail) return;
      detail.replaceChildren(
        elementNode("p", "detail-z", `Atomic number ${element.z}`),
        elementNode("div", "detail-symbol", element.symbol),
        elementNode("p", "detail-name", element.name)
      );
      const list = document.createElement("dl");
      const addPair = (term, value) => {
        list.append(elementNode("dt", "", term), elementNode("dd", "", value));
      };
      addPair("Mass", `${formatMass(element.mass)} g/mol`);
      addPair(
        "Source",
        element.standard
          ? "Abridged standard atomic weight (CIAAW 2024)"
          : "Most stable isotope mass number"
      );
      detail.append(list);
    };

    const updateCount = (shown) => {
      if (!count) return;
      count.textContent =
        shown === elements.length
          ? `${elements.length} elements`
          : `${shown} of ${elements.length} elements`;
    };

    render(elements);
    updateCount(elements.length);
    const initial = elements.find((element) => element.symbol === selected) || elements[0];
    if (initial) select(initial);

    if (search) {
      search.addEventListener("input", () => {
        const query = search.value.trim().toLowerCase();
        const filtered = query
          ? elements.filter((element) => {
              return (
                element.symbol.toLowerCase().includes(query) ||
                element.name.toLowerCase().includes(query) ||
                String(element.z) === query
              );
            })
          : elements;
        render(filtered);
        updateCount(filtered.length);
      });
    }
  }

  function initDocsNav() {
    const current = window.location.pathname;
    const currentFile = current.endsWith("/") ? "index.html" : current.split("/").pop();
    document.querySelectorAll("[data-docs-nav] a").forEach((link) => {
      const url = new URL(link.href, window.location.href);
      const fileName = url.pathname.split("/").pop();
      if (url.pathname === current || fileName === currentFile) {
        link.setAttribute("aria-current", "page");
      }
    });
  }

  function initYear() {
    document.querySelectorAll("[data-year]").forEach((node) => {
      node.textContent = String(new Date().getFullYear());
    });
  }

  initTheme();
  initNavigation();
  initCopyButtons();
  initElementExplorer();
  initDocsNav();
  initYear();
})();
