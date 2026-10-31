/* chemistry-engine playground: runs the real Python wheel via Pyodide. */
(() => {
  "use strict";

  const DEFAULT_ENGINE = {
    version: "0.1.0",
    wheel: "chemistry_engine-0.1.0-py3-none-any.whl",
    pyodide: "0.29.5",
  };

  const PYODIDE_HOSTS = [
    (version) => `https://fastly.jsdelivr.net/pyodide/v${version}/full/`,
    (version) => `https://gcore.jsdelivr.net/pyodide/v${version}/full/`,
    (version) => `https://unpkg.com/pyodide@${version}/`,
    (version) => `https://cdn.jsdelivr.net/pyodide/v${version}/full/`,
  ];

  const RUNNER = String.raw`
import json
from fractions import Fraction
from chemistry_engine import (
    Feed,
    balance_equation,
    elemental_analysis,
    molar_mass,
    parse_formula,
    stoichiometry,
)


def _num(value):
    if isinstance(value, Fraction):
        return int(value) if value.denominator == 1 else float(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _run(op, payload_json):
    try:
        payload = json.loads(payload_json)
        if op == "mass":
            formula = parse_formula(payload.get("formula", ""))
            return json.dumps({
                "ok": True,
                "formula": formula.text,
                "molar_mass": molar_mass(formula),
                "charge": formula.charge,
                "canonical": formula.canonical_formula(),
            })
        if op == "composition":
            formula = parse_formula(payload.get("formula", ""))
            rows = []
            for item in elemental_analysis(formula):
                rows.append({
                    "symbol": item.element.symbol,
                    "name": item.element.name,
                    "count": _num(item.count),
                    "mass": item.mass_g_per_mol,
                    "percent": item.percent,
                })
            return json.dumps({
                "ok": True,
                "formula": formula.text,
                "molar_mass": molar_mass(formula),
                "rows": rows,
            })
        if op == "balance":
            result = balance_equation(payload.get("equation", ""))
            checks = [
                {"symbol": check.symbol, "left": _num(check.left), "right": _num(check.right)}
                for check in result.element_balances
            ]
            return json.dumps({
                "ok": True,
                "formula": result.formula,
                "coefficients": list(result.coefficients),
                "unique": result.is_unique,
                "reversible": result.reversible,
                "checks": checks,
                "charge": {"left": result.charge_left, "right": result.charge_right},
            })
        if op == "stoich":
            feeds = [
                Feed(
                    item.get("species", ""),
                    float(item.get("amount", 0)),
                    item.get("unit") or "mol",
                )
                for item in payload.get("feeds", [])
            ]
            result = stoichiometry(payload.get("equation", ""), feeds)
            return json.dumps({
                "ok": True,
                "equation": result.equation.formula,
                "extent": result.extent,
                "limiting": list(result.limiting),
                "feed": result.feed_moles,
                "consumed": result.consumed,
                "remaining": result.remaining,
                "produced": result.produced,
                "product_masses": result.product_masses,
                "remaining_masses": result.remaining_masses,
                "reactants": [species.formula.text for species in result.equation.reactants],
                "products": [species.formula.text for species in result.equation.products],
            })
        return json.dumps({"ok": False, "error": "Unknown operation: " + str(op)})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
`;

  const EXAMPLES = {
    mass: { formula: "CuSO4·5H2O" },
    composition: { formula: "C6H12O6" },
    balance: { equation: "KMnO4 + HCl -> KCl + MnCl2 + Cl2 + H2O" },
    stoich: {
      equation: "N2 + 3H2 -> 2NH3",
      feeds: [
        { species: "N2", amount: "1", unit: "mol" },
        { species: "H2", amount: "2", unit: "mol" },
      ],
    },
  };

  const state = {
    op: "mass",
    engine: null,
    enginePromise: null,
    engineInfo: null,
    busy: false,
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const form = $("[data-playground-form]");
  const output = $("[data-playground-output]");
  if (!form || !output) return;

  // ------------------------------------------------------------------
  // formatting
  // ------------------------------------------------------------------
  function num(value) {
    if (typeof value !== "number" || !Number.isFinite(value)) return String(value);
    return Number(value.toPrecision(6)).toString();
  }

  function table(headers, rows) {
    const cells = rows.map((row) => row.map((cell) => String(cell)));
    const widths = headers.map((header, index) =>
      Math.max(header.length, ...cells.map((row) => row[index].length), 0)
    );
    const format = (row) =>
      row
        .map((cell, index) => String(cell).padEnd(widths[index]))
        .join("  ")
        .trimEnd();
    return [format(headers), ...cells.map(format)].join("\n");
  }

  function renderMass(data) {
    return [
      `${data.formula}`,
      "",
      `molar mass : ${num(data.molar_mass)} g/mol`,
      `charge     : ${data.charge}`,
      `canonical  : ${data.canonical}`,
    ].join("\n");
  }

  function renderComposition(data) {
    const rows = data.rows.map((row) => [
      row.symbol,
      row.name,
      num(row.count),
      num(row.mass),
      num(row.percent),
    ]);
    return [
      `${data.formula} — ${num(data.molar_mass)} g/mol`,
      "",
      table(["Element", "Name", "Atoms", "Mass (g/mol)", "Mass %"], rows),
    ].join("\n");
  }

  function renderBalance(data) {
    const lines = [data.formula, "", "Atom check (elements in equation order):"];
    data.checks.forEach((check) => {
      lines.push(`  ${check.symbol}: ${num(check.left)} = ${num(check.right)}`);
    });
    const charged = data.charge.left !== 0 || data.charge.right !== 0;
    lines.push(
      charged
        ? `Charge: ${data.charge.left} = ${data.charge.right}`
        : "Charge: neutral (0 = 0)"
    );
    if (!data.unique) {
      lines.push(
        "",
        "note: more than one independent balance exists; showing the smallest positive integer solution."
      );
    }
    return lines.join("\n");
  }

  function renderStoich(data) {
    const reactRows = data.reactants.map((label) => [
      label,
      num(data.feed[label] ?? 0),
      num(data.consumed[label] ?? 0),
      num(data.remaining[label] ?? 0),
      num(data.remaining_masses[label] ?? 0),
    ]);
    const productRows = data.products.map((label) => [
      label,
      num(data.produced[label] ?? 0),
      num(data.product_masses[label] ?? 0),
    ]);
    return [
      `Balanced equation: ${data.equation}`,
      `Reaction extent  : ${num(data.extent)} mol`,
      `Limiting reagent : ${data.limiting.join(", ")}`,
      "",
      "Reactants:",
      table(
        ["Species", "Fed (mol)", "Consumed (mol)", "Remaining (mol)", "Remaining (g)"],
        reactRows
      ),
      "",
      "Products:",
      table(["Species", "Produced (mol)", "Mass (g)"], productRows),
    ].join("\n");
  }

  function render(op, data) {
    if (op === "mass") return renderMass(data);
    if (op === "composition") return renderComposition(data);
    if (op === "balance") return renderBalance(data);
    return renderStoich(data);
  }

  // ------------------------------------------------------------------
  // engine status
  // ------------------------------------------------------------------
  function setStatus(kind, text) {
    const banner = $("[data-engine-banner]");
    if (banner) banner.dataset.state = kind;
    const label = $("[data-engine-status]");
    if (label) label.textContent = text;
  }

  async function fetchEngineInfo() {
    if (state.engineInfo) return state.engineInfo;
    try {
      const response = await fetch("assets/engine.json", { cache: "no-cache" });
      if (response.ok) {
        const info = await response.json();
        if (info && info.wheel && info.pyodide) {
          state.engineInfo = info;
          return info;
        }
      }
    } catch (error) {
      /* fall back to defaults below */
    }
    state.engineInfo = DEFAULT_ENGINE;
    return state.engineInfo;
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error(`Could not download ${src}`));
      document.head.appendChild(script);
    });
  }

  function ensureEngine() {
    if (state.engine) return Promise.resolve(state.engine);
    if (state.enginePromise) return state.enginePromise;

    state.enginePromise = (async () => {
      const info = await fetchEngineInfo();
      const failures = [];
      for (const makeBase of PYODIDE_HOSTS) {
        const base = makeBase(info.pyodide);
        const host = new URL(base).host;
        try {
          setStatus("loading", `Downloading Python runtime from ${host}…`);
          await loadScript(base + "pyodide.js");
          setStatus("loading", "Starting Python…");
          const pyodide = await window.loadPyodide({ indexURL: base });
          setStatus("loading", "Installing the chemistry-engine wheel…");
          await pyodide.loadPackage("micropip");
          const micropip = pyodide.pyimport("micropip");
          const wheelUrl = new URL("assets/" + info.wheel, window.location.href).href;
          await micropip.install(wheelUrl);
          pyodide.runPython(RUNNER);
          state.engine = pyodide;
          setStatus("ready", `Engine ready · chemistry-engine ${info.version}`);
          return pyodide;
        } catch (error) {
          failures.push(`${host}: ${error && error.message ? error.message : error}`);
          try {
            delete window.loadPyodide;
          } catch (error) {
            /* ignore */
          }
        }
      }
      const detail = failures.join(" · ") || "unknown error";
      throw new Error(
        "Could not load Pyodide. Check the network connection or try again. " + detail
      );
    })().catch((error) => {
      state.enginePromise = null;
      setStatus("error", "Engine failed to load");
      throw error;
    });
    return state.enginePromise;
  }

  // ------------------------------------------------------------------
  // inputs
  // ------------------------------------------------------------------
  function feedRow(feed = { species: "", amount: "", unit: "mol" }) {
    const row = document.createElement("div");
    row.className = "feed-row";
    row.innerHTML =
      '<input type="text" data-feed-species placeholder="Species" aria-label="Feed species" autocomplete="off">' +
      '<input type="number" data-feed-amount step="any" placeholder="Amount" aria-label="Feed amount">' +
      '<select data-feed-unit aria-label="Feed unit">' +
      '<option value="mol">mol</option><option value="mmol">mmol</option><option value="umol">umol</option>' +
      '<option value="g">g</option><option value="kg">kg</option><option value="mg">mg</option><option value="ug">ug</option>' +
      "</select>" +
      '<button type="button" class="feed-remove" data-remove-feed aria-label="Remove feed">×</button>';
    $("[data-feed-species]", row).value = feed.species;
    $("[data-feed-amount]", row).value = feed.amount;
    $("[data-feed-unit]", row).value = feed.unit;
    return row;
  }

  function resetFeeds(feeds) {
    const container = $("[data-feeds]");
    if (!container) return;
    container.replaceChildren(...feeds.map((feed) => feedRow(feed)));
  }

  function addFeedRow() {
    const container = $("[data-feeds]");
    if (container) container.appendChild(feedRow());
  }

  function collectPayload() {
    if (state.op === "mass" || state.op === "composition") {
      const input = $(`[data-panel="${state.op}"] [data-formula]`);
      const formula = input.value.trim();
      if (!formula) return { error: "Enter a formula first." };
      return { formula };
    }
    if (state.op === "balance") {
      const equation = $('[data-panel="balance"] [data-equation]').value.trim();
      if (!equation) return { error: "Enter an equation first." };
      return { equation };
    }
    const equation = $('[data-panel="stoich"] [data-equation]').value.trim();
    if (!equation) return { error: "Enter an equation first." };
    const feeds = $$('[data-panel="stoich"] .feed-row')
      .map((row) => ({
        species: $("[data-feed-species]", row).value.trim(),
        amount: $("[data-feed-amount]", row).value.trim(),
        unit: $("[data-feed-unit]", row).value,
      }))
      .filter((feed) => feed.species && feed.amount);
    if (!feeds.length) return { error: "Add at least one reactant feed." };
    return { equation, feeds };
  }

  function switchOp(op) {
    state.op = op;
    $$("[data-op]").forEach((button) => {
      button.setAttribute("aria-selected", String(button.dataset.op === op));
    });
    $$("[data-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== op;
    });
  }

  function setBusy(busy) {
    state.busy = busy;
    const run = $("[data-run]");
    if (run) {
      run.disabled = busy;
      run.textContent = busy ? "Running…" : "Run";
    }
    $$("[data-playground-form] input, [data-playground-form] select, [data-playground-form] button").forEach(
      (control) => {
        if (control === run) return;
        control.disabled = busy;
      }
    );
  }

  async function runOperation() {
    if (state.busy) return;
    const payload = collectPayload();
    if (payload.error) {
      output.textContent = payload.error;
      return;
    }
    setBusy(true);
    output.textContent = "Working…";
    try {
      const pyodide = await ensureEngine();
      const runner = pyodide.globals.get("_run");
      let raw;
      try {
        raw = runner(state.op, JSON.stringify(payload));
      } finally {
        if (runner && typeof runner.destroy === "function") runner.destroy();
      }
      const data = JSON.parse(raw);
      if (!data.ok) {
        output.textContent = `Could not compute this.\n\n${data.error}`;
        return;
      }
      output.textContent = render(state.op, data);
    } catch (error) {
      output.textContent =
        "Could not start the engine.\n\n" +
        (error && error.message ? error.message : error) +
        "\n\nThe first run downloads Pyodide (about 12 MB) and the engine wheel from this site.";
      setStatus("error", "Engine failed to load");
    } finally {
      setBusy(false);
    }
  }

  function loadExample() {
    const example = EXAMPLES[state.op];
    if (!example) return;
    if (state.op === "mass" || state.op === "composition") {
      $(`[data-panel="${state.op}"] [data-formula]`).value = example.formula;
    } else if (state.op === "balance") {
      $('[data-panel="balance"] [data-equation]').value = example.equation;
    } else {
      $('[data-panel="stoich"] [data-equation]').value = example.equation;
      resetFeeds(example.feeds);
    }
    runOperation();
  }

  // ------------------------------------------------------------------
  // wiring
  // ------------------------------------------------------------------
  $$("[data-op]").forEach((button) => {
    button.addEventListener("click", () => switchOp(button.dataset.op));
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runOperation();
  });

  const exampleButton = $("[data-example]");
  if (exampleButton) exampleButton.addEventListener("click", loadExample);

  const addFeed = $("[data-add-feed]");
  if (addFeed) addFeed.addEventListener("click", addFeedRow);

  const feeds = $("[data-feeds]");
  if (feeds) {
    feeds.addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-feed]");
      if (!button) return;
      const row = button.closest(".feed-row");
      if (!row) return;
      if (feeds.children.length === 1) {
        $("[data-feed-species]", row).value = "";
        $("[data-feed-amount]", row).value = "";
      } else {
        row.remove();
      }
    });
  }

  const copyButton = $("[data-copy-output]");
  if (copyButton) {
    copyButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(output.textContent);
        copyButton.textContent = "Copied!";
        window.setTimeout(() => {
          copyButton.textContent = "Copy";
        }, 1500);
      } catch (error) {
        /* clipboard unavailable */
      }
    });
  }

  switchOp("mass");
  setStatus(
    "idle",
    "Python runtime not loaded. The first run downloads about 12 MB from a CDN."
  );

  const demo = new URLSearchParams(window.location.search).get("demo");
  if (demo && EXAMPLES[demo]) {
    switchOp(demo);
    loadExample();
  }
})();
