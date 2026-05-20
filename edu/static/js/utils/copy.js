(() => {
const getCookie = (name) => {
  const cookies = document.cookie ? document.cookie.split("; ") : [];
  for (const c of cookies) {
    const [key, ...rest] = c.split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return "";
};

const copyIconMarkupValue = `
  <span class="llm-copy-btn__icon llm-copy-btn__icon--copy" aria-hidden="true">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="9" y="9" width="11" height="11" rx="2"></rect>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
    </svg>
  </span>
  <span class="llm-copy-btn__icon llm-copy-btn__icon--check" aria-hidden="true">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.3">
      <path stroke-linecap="round" stroke-linejoin="round" d="M5 12.5l4.2 4.2L19 7.2"></path>
    </svg>
  </span>
`.trim();

const copyTextToClipboard = async (text) => {
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch (error) {
      // Fall through to legacy copy when permission is blocked.
    }
  }
  // Clipboard API fallback for older browsers.
  const helper = document.createElement("textarea");
  helper.value = text;
  helper.setAttribute("readonly", "");
  helper.style.position = "fixed";
  helper.style.top = "-9999px";
  helper.style.left = "-9999px";
  document.body.appendChild(helper);
  helper.focus();
  helper.select();
  const success = document.execCommand("copy");
  helper.remove();
  if (!success) {
    throw new Error("copy-failed");
  }
};

const setCopyButtonFeedback = (button, copied, resetDelay) => {
  if (!button) return;
  if (button._copyFeedbackTimer) {
    window.clearTimeout(button._copyFeedbackTimer);
  }

  button.classList.remove("is-copied", "is-copy-failed");
  button.classList.add(copied ? "is-copied" : "is-copy-failed");
  const defaultLabel = button.getAttribute("data-copy-default") || "Copy";
  const copiedLabel = button.getAttribute("data-copy-copied") || "Copied";
  const failedLabel = button.getAttribute("data-copy-failed") || "Copy failed";
  const activeLabel = copied ? copiedLabel : failedLabel;

  button.setAttribute("aria-label", activeLabel);
  button.setAttribute("title", activeLabel);

  if (!Number.isFinite(resetDelay) || resetDelay <= 0) return;

  button._copyFeedbackTimer = window.setTimeout(() => {
    button.classList.remove("is-copied", "is-copy-failed");
    button.setAttribute("aria-label", defaultLabel);
    button.setAttribute("title", defaultLabel);
  }, resetDelay);
};

const resolveResetDelay = (button, options) => {
  if (options && Number.isFinite(options.resetDelay)) {
    return options.resetDelay;
  }
  if (button) {
    const attr = button.getAttribute("data-copy-reset");
    if (attr) {
      const parsed = Number.parseInt(attr, 10);
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return 1200;
};

const extractTextFromTarget = (target) => {
  if (!target) return "";
  if (typeof target.value === "string") return target.value;
  if (typeof target.textContent === "string") return target.textContent;
  if (typeof target.innerText === "string") return target.innerText;
  return "";
};

const resolveCopyText = (button) => {
  if (!button) return "";

  const directText = button.getAttribute("data-copy-text");
  if (directText) return directText;

  const targetSelector = button.getAttribute("data-copy-target");
  if (targetSelector) {
    const targetEl = document.querySelector(targetSelector);
    const targetText = extractTextFromTarget(targetEl).trim();
    if (targetText) return targetText;
  }

  if (button._copyTarget && document.contains(button._copyTarget)) {
    const targetText = extractTextFromTarget(button._copyTarget).trim();
    if (targetText) return targetText;
  }

  if (button.classList.contains("llm-copy-code")) {
    const wrap = button.closest(".llm-code-block-wrap");
    const codeEl = wrap ? wrap.querySelector("pre code, pre") : null;
    const codeText = extractTextFromTarget(codeEl).trim();
    if (codeText) return codeText;
  }

  const scope = button.getAttribute("data-copy-scope");
  if (scope) {
    let bubbleEl = button.closest(".llm-chat-bubble");
    if (!bubbleEl) {
      const entryEl = button.closest(".llm-chat-entry");
      if (entryEl) {
        bubbleEl = entryEl.querySelector(
          scope === "prompt" ? ".llm-chat-bubble--user" : ".llm-chat-bubble--ai"
        );
      }
    }
    const messageEl = bubbleEl?.querySelector(".llm-chat-msg");
    const messageText = extractTextFromTarget(messageEl).trim();
    if (messageText) return messageText;
  }

  return "";
};

const resolveSelectionTarget = (button) => {
  if (!button) return null;
  const targetSelector = button.getAttribute("data-copy-target");
  if (targetSelector) {
    const targetEl = document.querySelector(targetSelector);
    if (targetEl && typeof targetEl.select === "function") return targetEl;
  }
  if (button._copyTarget && typeof button._copyTarget.select === "function") {
    return button._copyTarget;
  }
  return null;
};

const updateCopyStatus = (button, copied) => {
  if (!button) return;
  const statusSelector = button.getAttribute("data-copy-status");
  if (!statusSelector) return;
  const statusEl = document.querySelector(statusSelector);
  if (!statusEl) return;
  const successText = button.getAttribute("data-copy-status-copied") || "Copied to clipboard.";
  const failText = button.getAttribute("data-copy-status-failed") || "Copy failed.";
  statusEl.textContent = copied ? successText : failText;
};

const copyIconMarkup = copyIconMarkupValue;

const handleCopy = async (button, text, options = {}) => {
  if (!button || !text) return false;
  let copied = false;
  try {
    await copyTextToClipboard(text);
    copied = true;
  } catch (error) {
    copied = false;
  }
  const resetDelay = resolveResetDelay(button, options);
  setCopyButtonFeedback(button, copied, resetDelay);
  updateCopyStatus(button, copied);
  if (!copied) {
    const selectionTarget = resolveSelectionTarget(button);
    if (selectionTarget) selectionTarget.select();
  }
  return copied;
};

const overlayRegistry = new WeakMap();
const overlayStates = new Set();
let copySourceCounter = 0;

const ensureOverlayLayer = (host) => {
  if (!host) return null;
  host.classList.add("copy-overlay-host");
  const existing = Array.from(host.children || []).find((child) =>
    child.classList && child.classList.contains("copy-overlay-layer")
  );
  if (existing) return existing;

  const layer = document.createElement("div");
  layer.className = "copy-overlay-layer";
  host.appendChild(layer);
  return layer;
};

const resolveCodeTarget = (codeEl) => {
  if (!codeEl) return null;
  if (codeEl.tagName === "CODE") return codeEl;
  const nestedCode = codeEl.querySelector("code");
  return nestedCode || codeEl;
};

const ensureCopySourceId = (targetEl) => {
  if (!targetEl) return "";
  const existing = targetEl.getAttribute("data-copy-source-id");
  if (existing) return existing;
  copySourceCounter += 1;
  const nextId = `copy-source-${copySourceCounter}`;
  targetEl.setAttribute("data-copy-source-id", nextId);
  return nextId;
};

const resolveAnchorElement = (codeEl, state) => {
  if (!codeEl) return null;
  if (!state || !state.anchorSelector) return codeEl;
  return codeEl.closest(state.anchorSelector) || codeEl;
};

const updateOverlay = (state) => {
  if (!state || !state.root || !state.layer) return;
  const codeBlocks = Array.from(state.root.querySelectorAll(state.codeSelector));
  state.layer.innerHTML = "";
  if (!codeBlocks.length) {
    if (state.scrollContainer && state.scrollContainer.style) {
      state.scrollContainer.style.paddingBottom = "";
    }
    return;
  }

  let anyOutputVisible = false;

  const layerRect = state.layer.getBoundingClientRect();
  codeBlocks.forEach((codeEl) => {
    const codeRect = codeEl.getBoundingClientRect();
    if (!codeRect.width || !codeRect.height) return;
    if (codeRect.bottom < layerRect.top || codeRect.top > layerRect.bottom) return;
    const anchorEl = resolveAnchorElement(codeEl, state);
    const anchorRect = anchorEl ? anchorEl.getBoundingClientRect() : codeRect;

    const offsetX = Number.isFinite(state.offsetX) ? state.offsetX : 8;
    const offsetY = Number.isFinite(state.offsetY) ? state.offsetY : 8;

    if (state.enableCodeRunner) {
      // 1. Controls container (Run & Copy buttons on the right edge)
      const controls = document.createElement("div");
      controls.className = "code-block-controls";
      controls.style.top = `${Math.max(0, anchorRect.top - layerRect.top) + offsetY}px`;
      controls.style.left = `${Math.max(0, anchorRect.right - layerRect.left) - offsetX}px`;

      // 2. Language dropdown (floating on the left edge)
      const select = document.createElement("select");
      select.className = "code-lang-select";
      select.setAttribute("aria-label", "Select programming language");

      const languages = [
        { value: "python", label: "Py" },
        { value: "javascript", label: "JS" },
        { value: "c++", label: "C" }
      ];

      languages.forEach((lang) => {
        const option = document.createElement("option");
        option.value = lang.value;
        option.textContent = lang.label;
        select.appendChild(option);
      });

      // Get saved language or detect
      let currentLang = codeEl.getAttribute("data-language");
      if (!currentLang) {
        // Auto-detect based on contents
        const text = codeEl.textContent;
        if (text.includes("console.log") || text.includes("const ") || text.includes("let ") || text.includes("function ")) {
          currentLang = "javascript";
        } else if (text.includes("#include") || text.includes("std::") || text.includes("cout") || text.includes("printf")) {
          currentLang = "c++";
        } else {
          currentLang = "python";
        }
        codeEl.setAttribute("data-language", currentLang);
      }
      select.value = currentLang;

      // Handle language change
      select.addEventListener("change", (e) => {
        const newLang = select.value;
        codeEl.setAttribute("data-language", newLang);
        // Dispatch custom event to notify editor to save
        const changeEvent = new CustomEvent("code-block-language-change", {
          bubbles: true,
          detail: { codeEl, language: newLang }
        });
        select.dispatchEvent(changeEvent);
      });

      // 3. Run button
      const runBtn = document.createElement("button");
      runBtn.type = "button";
      runBtn.className = "code-run-btn";

      const isRunning = codeEl.dataset.runStatus === "running";

      runBtn.setAttribute("aria-label", isRunning ? "Running code" : "Run code");
      runBtn.setAttribute("title", isRunning ? "Running" : "Run");
      runBtn.disabled = isRunning;

      if (isRunning) {
        runBtn.innerHTML = `
          <span class="code-run-btn__icon" aria-hidden="true">
            <svg class="animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <circle cx="12" cy="12" r="10" stroke-dasharray="30 30" stroke-linecap="round"></circle>
            </svg>
          </span>`;
      } else {
        runBtn.innerHTML = `
          <span class="code-run-btn__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M8 5.5v13l10-6.5-10-6.5Z" fill="currentColor"></path>
            </svg>
          </span>`;
      }

      runBtn.addEventListener("click", async () => {
        if (codeEl.dataset.runStatus === "running") return;

        codeEl.dataset.runStatus = "running";
        // Re-schedule update to show spinner
        state.scheduleUpdate();

        try {
          const codeText = codeEl.textContent.trim();
          const language = codeEl.getAttribute("data-language") || "python";

          const res = await fetch("/api/execute-code/", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCookie("csrftoken"),
            },
            credentials: "same-origin",
            body: JSON.stringify({ code: codeText, language }),
          });

          const data = await res.json();

          if (data.error) {
            codeEl.dataset.runOutputError = "true";
            codeEl.dataset.runOutput = `Error: ${data.error}`;
          } else {
            const stdout = data.stdout || "";
            const stderr = data.stderr || "";
            const exitCode = data.exit_code ?? 0;

            codeEl.dataset.runOutputError = exitCode !== 0 ? "true" : "false";
            if (!stdout && !stderr) {
              codeEl.dataset.runOutput = exitCode === 0
                ? "Ran successfully (no output)"
                : `Exited with code ${exitCode}`;
            } else {
              codeEl.dataset.runOutput = stdout + (stderr ? `\n─── stderr ───\n${stderr}` : "");
            }
          }
          codeEl.dataset.runOutputVisible = "true";
        } catch (err) {
          codeEl.dataset.runOutputError = "true";
          codeEl.dataset.runOutput = `Network error: ${err.message}`;
          codeEl.dataset.runOutputVisible = "true";
        } finally {
          codeEl.dataset.runStatus = "idle";
          // Re-schedule update to refresh spinner and show output panel
          state.scheduleUpdate();

          // Wait a frame for DOM update & padding to apply, then scroll to bottom
          setTimeout(() => {
            if (state.scrollContainer) {
              const container = state.scrollContainer;
              const targetScrollTop = codeEl.offsetTop + codeEl.offsetHeight + 220 - container.clientHeight;
              if (targetScrollTop > container.scrollTop) {
                container.scrollTo({
                  top: targetScrollTop,
                  behavior: "smooth"
                });
              }
            }
          }, 150);
        }
      });

      // 4. Copy button
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "llm-copy-btn llm-copy-code";
      copyBtn.setAttribute("aria-label", "Copy code");
      copyBtn.setAttribute("title", "Copy code");
      copyBtn.setAttribute("data-copy-default", "Copy code");
      copyBtn.setAttribute("data-copy-copied", "Copied");
      copyBtn.setAttribute("data-copy-failed", "Copy failed");
      copyBtn.innerHTML = copyIconMarkupValue;

      const targetEl = resolveCodeTarget(codeEl);
      copyBtn._copyTarget = targetEl;
      const sourceId = ensureCopySourceId(targetEl);
      if (sourceId) {
        copyBtn.setAttribute("data-copy-target", `[data-copy-source-id="${sourceId}"]`);
      }

      // Append buttons to controls on the right
      controls.appendChild(runBtn);
      controls.appendChild(copyBtn);
      state.layer.appendChild(controls);

      // Position and append select on the left
      select.style.position = "absolute";
      select.style.top = `${Math.max(0, anchorRect.top - layerRect.top) + offsetY}px`;
      select.style.left = `${Math.max(0, anchorRect.left - layerRect.left) + offsetX}px`;
      select.style.zIndex = "5";
      state.layer.appendChild(select);

      // Hide / show based on content
      const hasCode = codeEl.textContent.trim().length > 0;
      runBtn.style.display = hasCode ? "inline-flex" : "none";
      select.style.display = hasCode ? "inline-block" : "none";

      // 5. Output Panel
      if (codeEl.dataset.runOutputVisible === "true") {
        anyOutputVisible = true;
        const outputPanel = document.createElement("div");
        outputPanel.className = "code-output-panel";
        if (codeEl.dataset.runOutputError === "true") {
          outputPanel.classList.add("code-output-panel--error");
        }

        outputPanel.innerHTML = `
          <div class="code-output-panel__header">
            <span class="code-output-panel__title">Output</span>
            <button type="button" class="code-output-panel__close" aria-label="Close output">✕</button>
          </div>
          <pre class="code-output-panel__body"></pre>`;

        const outputBody = outputPanel.querySelector(".code-output-panel__body");
        outputBody.textContent = codeEl.dataset.runOutput || "";

        const closeBtn = outputPanel.querySelector(".code-output-panel__close");
        closeBtn.addEventListener("click", () => {
          codeEl.dataset.runOutputVisible = "false";
          state.scheduleUpdate();
        });

        // Position output panel below code block inside the reserved flow margin-bottom
        outputPanel.style.position = "absolute";
        outputPanel.style.top = `${codeRect.bottom - layerRect.top + 8}px`;
        outputPanel.style.left = `${codeRect.left - layerRect.left}px`;
        outputPanel.style.width = `${codeRect.width}px`;
        outputPanel.style.pointerEvents = "auto";
        outputPanel.style.zIndex = "4";

        state.layer.appendChild(outputPanel);
      }
    } else {
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "llm-copy-btn llm-copy-code";
      copyBtn.setAttribute("aria-label", "Copy code");
      copyBtn.setAttribute("title", "Copy code");
      copyBtn.setAttribute("data-copy-default", "Copy code");
      copyBtn.setAttribute("data-copy-copied", "Copied");
      copyBtn.setAttribute("data-copy-failed", "Copy failed");
      copyBtn.innerHTML = copyIconMarkupValue;

      const targetEl = resolveCodeTarget(codeEl);
      copyBtn._copyTarget = targetEl;
      const sourceId = ensureCopySourceId(targetEl);
      if (sourceId) {
        copyBtn.setAttribute("data-copy-target", `[data-copy-source-id="${sourceId}"]`);
      }

      copyBtn.style.top = `${Math.max(0, anchorRect.top - layerRect.top) + offsetY}px`;
      copyBtn.style.left = `${Math.max(0, anchorRect.right - layerRect.left) - offsetX}px`;

      state.layer.appendChild(copyBtn);
    }
  });

  if (state.scrollContainer && state.scrollContainer.style) {
    if (anyOutputVisible) {
      state.scrollContainer.style.paddingBottom = "260px";
    } else {
      state.scrollContainer.style.paddingBottom = "";
    }
  }
};

const scheduleOverlayUpdate = (state) => {
  if (!state) return;
  if (state.raf) return;
  state.raf = window.requestAnimationFrame(() => {
    state.raf = null;
    updateOverlay(state);
  });
};

const registerCodeCopyOverlay = (options = {}) => {
  const root = options.root || document;
  const host = options.host || root;
  if (!root || !host) return null;

  const existing = overlayRegistry.get(host);
  if (existing) {
    existing.root = root;
    existing.codeSelector = options.codeSelector || existing.codeSelector;
    existing.scrollContainer = options.scrollContainer || existing.scrollContainer;
    if (typeof options.anchorSelector === "string") {
      existing.anchorSelector = options.anchorSelector;
    }
    if (Number.isFinite(options.offsetX)) existing.offsetX = options.offsetX;
    if (Number.isFinite(options.offsetY)) existing.offsetY = options.offsetY;
    if (options.enableCodeRunner !== undefined) {
      existing.enableCodeRunner = !!options.enableCodeRunner;
    }
    scheduleOverlayUpdate(existing);
    return existing;
  }

  const layer = ensureOverlayLayer(host);
  if (!layer) return null;

  const state = {
    root,
    host,
    layer,
    codeSelector: options.codeSelector || "pre",
    scrollContainer: options.scrollContainer || root,
    anchorSelector: typeof options.anchorSelector === "string" ? options.anchorSelector : null,
    offsetX: Number.isFinite(options.offsetX) ? options.offsetX : 8,
    offsetY: Number.isFinite(options.offsetY) ? options.offsetY : 8,
    enableCodeRunner: !!options.enableCodeRunner,
    raf: null,
    observer: null,
  };

  overlayRegistry.set(host, state);
  overlayStates.add(state);

  state.scheduleUpdate = () => scheduleOverlayUpdate(state);

  const scrollTarget = state.scrollContainer === window ? window : state.scrollContainer;
  if (scrollTarget && scrollTarget.addEventListener) {
    scrollTarget.addEventListener("scroll", state.scheduleUpdate, { passive: true });
  }
  window.addEventListener("resize", state.scheduleUpdate);

  if (typeof MutationObserver !== "undefined") {
    state.observer = new MutationObserver(state.scheduleUpdate);
    state.observer.observe(root, { childList: true, subtree: true });
  }

  state.scheduleUpdate();
  return state;
};

const refreshCodeCopyOverlays = () => {
  overlayStates.forEach((state) => state.scheduleUpdate && state.scheduleUpdate());
};

if (typeof document !== "undefined") {
  document.addEventListener("click", async (event) => {
    const button = event.target.closest(
      ".llm-copy-btn, [data-copy-target], [data-copy-text], [data-copy-scope]"
    );
    if (!button) return;
    if (button.classList.contains("code-run-btn")) return;
    if (button.disabled || button.getAttribute("aria-disabled") === "true") return;
    event.preventDefault();
    const textToCopy = resolveCopyText(button).trim();
    if (!textToCopy) return;
    await handleCopy(button, textToCopy);
  });
}

if (typeof window !== "undefined") {
  window.copyUtils = {
    handleCopy,
    copyIconMarkup,
    registerCodeCopyOverlay,
    refreshCodeCopyOverlays,
  };
}
})();
