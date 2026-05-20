(() => {
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
  if (!codeBlocks.length) return;

  const layerRect = state.layer.getBoundingClientRect();
  codeBlocks.forEach((codeEl) => {
    const codeRect = codeEl.getBoundingClientRect();
    if (!codeRect.width || !codeRect.height) return;
    if (codeRect.bottom < layerRect.top || codeRect.top > layerRect.bottom) return;
    const anchorEl = resolveAnchorElement(codeEl, state);
    const anchorRect = anchorEl ? anchorEl.getBoundingClientRect() : codeRect;

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
      copyBtn.setAttribute("data-copy-target", `[data-copy-source-id=\"${sourceId}\"]`);
    }

    const offsetX = Number.isFinite(state.offsetX) ? state.offsetX : 8;
    const offsetY = Number.isFinite(state.offsetY) ? state.offsetY : 8;
    copyBtn.style.top = `${Math.max(0, anchorRect.top - layerRect.top) + offsetY}px`;
    copyBtn.style.left = `${Math.max(0, anchorRect.right - layerRect.left) - offsetX}px`;

    state.layer.appendChild(copyBtn);
  });
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
