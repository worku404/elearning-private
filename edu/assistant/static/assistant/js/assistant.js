// Extracted from assistant/llm.html — URLs supplied via data-* attributes on #assistant-panel
  const bodyEl = document.body;
  const assistantPanel = document.getElementById("assistant-panel");
  const assistantLauncher = document.getElementById("assistant-unhide");
  // const assistantHideBtn = document.getElementById("assistant-hide-btn");
  const assistantCloseBtn = document.getElementById("assistant-close-btn");
  const assistantHistoryToggle = document.querySelector("[data-assistant-history-toggle]");
  const assistantHistoryShell = document.querySelector("[data-assistant-history-shell]");
  const assistantHistorySidebar = document.querySelector("[data-assistant-history-sidebar]");
  const assistantUiStateKey = "assistant_ui_state";
  const assistantSidebarWidthKey = "assistant_sidebar_width";
  const assistantHistoryOpenKey = "assistant_history_open";
  const desktopMediaQuery = window.matchMedia
    ? window.matchMedia("(min-width: 901px)")
    : null;

  const persistAssistantState = (state) => {
    try {
      localStorage.setItem(assistantUiStateKey, state);
    } catch (error) {
      // Ignore storage failures (private mode / blocked storage).
    }
  };

  const readAssistantState = () => {
    try {
      const stored = localStorage.getItem(assistantUiStateKey);
      if (stored === "hidden" || stored === "inline" || stored === "sidebar") {
        return stored;
      }
    } catch (error) {
      // Ignore storage failures.
    }
    return "hidden";
  };

  const persistHistoryState = (isOpen) => {
    try {
      localStorage.setItem(assistantHistoryOpenKey, isOpen ? "open" : "closed");
    } catch (error) {
      // Ignore storage failures.
    }
  };

  const readHistoryState = () => {
    try {
      const stored = localStorage.getItem(assistantHistoryOpenKey);
      if (stored === "open") return true;
      if (stored === "closed") return false;
    } catch (error) {
      // Ignore storage failures.
    }
    return true;
  };

  const setHistoryState = (isOpen, { persist = true } = {}) => {
    if (!assistantPanel) return;
    const nextOpen = Boolean(isOpen);
    assistantPanel.classList.toggle("assistant-history-open", nextOpen);
    if (assistantHistorySidebar) {
      assistantHistorySidebar.setAttribute("aria-hidden", String(!nextOpen));
    }
    if (assistantHistoryToggle) {
      assistantHistoryToggle.setAttribute("aria-expanded", String(nextOpen));
    }
    if (persist) {
      persistHistoryState(nextOpen);
    }
  };

  const updateAssistantOffset = () => {
    const header = document.getElementById("header");
    const offset = header ? header.offsetHeight : 0;
    document.documentElement.style.setProperty("--assistant-top-offset", `${offset}px`);
  };

  const syncAssistantLauncher = () => {
    if (!assistantLauncher) return;
    const isHidden = bodyEl.classList.contains("assistant-hidden");
    assistantLauncher.setAttribute("aria-expanded", String(!isHidden));
  };

  const setAssistantState = (state, { persist = true } = {}) => {
    const nextState = state === "sidebar" || state === "inline" ? state : "hidden";
    bodyEl.classList.toggle("assistant-hidden", nextState === "hidden");
    bodyEl.classList.toggle("assistant-sidebar-open", nextState === "sidebar");
    if (nextState !== "sidebar") {
      bodyEl.classList.remove("assistant-resizing");
    }
    if (persist) {
      persistAssistantState(nextState);
    }
    syncAssistantLauncher();
    if (nextState === "sidebar") {
      window.requestAnimationFrame(updateScrollBottomVisibility);
    }
  };

  const showInlineAssistant = () => {
    setAssistantState("inline");
  };

  const hideAssistant = () => {
    setAssistantState("hidden");
  };

  const openAssistantSidebar = () => {
    setAssistantState("sidebar");
    restoreAssistantSidebarDimensions();
  };

  const focusAssistantPrompt = () => {
    const prompt = document.getElementById("id_prompt");
    if (!prompt) return;
    prompt.focus();
    // Keep caret at end of existing text for quick continuation.
    if (typeof prompt.setSelectionRange === "function") {
      const end = (prompt.value || "").length;
      prompt.setSelectionRange(end, end);
    }
  };

  const isEditableTarget = (target) => {
    if (!target) return false;
    const tagName = target.tagName;
    // Do not steal Ctrl/Cmd+B while user is typing in editable controls.
    return target.isContentEditable || tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT";
  };

  const toggleAssistantSidebar = () => {
    const isHidden = bodyEl.classList.contains("assistant-hidden");
    const isSidebarOpen = bodyEl.classList.contains("assistant-sidebar-open");
    // Toggle between hidden and sidebar-open states.
    if (!isHidden && isSidebarOpen) {
      hideAssistant();
      return;
    }
    openAssistantSidebar();
    focusAssistantPrompt();
  };

  const parseCssPx = (value, fallback) => {
    const parsed = Number.parseFloat(String(value || "").trim());
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  const readCssVar = (name) => {
    const rootStyles = getComputedStyle(document.documentElement);
    const rootValue = rootStyles.getPropertyValue(name);
    if (rootValue && rootValue.trim()) return rootValue;
    if (document.body) {
      const bodyValue = getComputedStyle(document.body).getPropertyValue(name);
      if (bodyValue && bodyValue.trim()) return bodyValue;
    }
    return "";
  };

  const getAssistantSidebarLimits = () => {
    const minWidth = parseCssPx(readCssVar("--assistant-sidebar-min-width"), 320);
    const maxWidth = parseCssPx(readCssVar("--assistant-sidebar-max-width"), 720);
    return { minWidth, maxWidth };
  };

  const clampValue = (value, min, max) => Math.min(Math.max(value, min), max);

  const getStoredAssistantWidth = () => {
    try {
      const stored = localStorage.getItem(assistantSidebarWidthKey);
      const parsed = Number.parseFloat(stored);
      return Number.isFinite(parsed) ? parsed : null;
    } catch (error) {
      return null;
    }
  };

  const clearAssistantSidebarWidth = () => {
    document.documentElement.style.removeProperty("--assistant-sidebar-width");
    if (document.body) {
      document.body.style.removeProperty("--assistant-sidebar-width");
    }
  };

  const applyAssistantSidebarWidth = (value, { persist = false } = {}) => {
    if (desktopMediaQuery && !desktopMediaQuery.matches) return;
    const { minWidth, maxWidth } = getAssistantSidebarLimits();
    const viewportMax = Math.max(minWidth, Math.min(maxWidth, window.innerWidth - 80));
    const clamped = clampValue(value, minWidth, viewportMax);
    document.documentElement.style.setProperty("--assistant-sidebar-width", `${clamped}px`);
    if (document.body) {
      document.body.style.setProperty("--assistant-sidebar-width", `${clamped}px`);
    }
    if (persist) {
      try {
        localStorage.setItem(assistantSidebarWidthKey, String(Math.round(clamped)));
      } catch (error) {
        // Ignore storage failures.
      }
    }
  };

  const clampSidebarPosition = () => {
    if (!assistantPanel || !bodyEl.classList.contains("assistant-sidebar-open")) return;
    if (desktopMediaQuery && !desktopMediaQuery.matches) return;

    const width = assistantPanel.offsetWidth || 440;
    const height = assistantPanel.offsetHeight || 600;
    let left = parseFloat(assistantPanel.style.left) || (window.innerWidth - width - 24);
    let top = parseFloat(assistantPanel.style.top) || 80;

    left = Math.max(16, Math.min(window.innerWidth - width - 16, left));
    top = Math.max(16, Math.min(window.innerHeight - height - 16, top));

    assistantPanel.style.left = `${left}px`;
    assistantPanel.style.top = `${top}px`;
    assistantPanel.style.right = "auto";
  };

  const restoreAssistantSidebarDimensions = () => {
    if (!assistantPanel) return;
    if (desktopMediaQuery && !desktopMediaQuery.matches) {
      assistantPanel.style.left = "";
      assistantPanel.style.top = "";
      assistantPanel.style.width = "";
      assistantPanel.style.height = "";
      assistantPanel.style.right = "";
      return;
    }

    try {
      const storedLeft = localStorage.getItem("assistant_float_left");
      const storedTop = localStorage.getItem("assistant_float_top");
      const storedWidth = localStorage.getItem("assistant_float_width");
      const storedHeight = localStorage.getItem("assistant_float_height");

      if (storedWidth) assistantPanel.style.width = storedWidth;
      if (storedHeight) assistantPanel.style.height = storedHeight;
      if (storedLeft) assistantPanel.style.left = storedLeft;
      if (storedTop) assistantPanel.style.top = storedTop;

      if (storedLeft || storedTop || storedWidth || storedHeight) {
        assistantPanel.style.right = "auto";
        clampSidebarPosition();
        return;
      }
    } catch (e) {}

    // Default centered-right fallback
    const width = 440;
    const topOffset = parseCssPx(readCssVar("--assistant-top-offset"), 64) + 16;
    const defaultLeft = window.innerWidth - width - 24;
    const defaultHeight = window.innerHeight - topOffset - 24;

    assistantPanel.style.width = `${width}px`;
    assistantPanel.style.height = `${defaultHeight}px`;
    assistantPanel.style.left = `${defaultLeft}px`;
    assistantPanel.style.top = `${topOffset}px`;
    assistantPanel.style.right = "auto";
  };

  const getCurrentSidebarWidth = () => {
    const fromVar = parseCssPx(readCssVar("--assistant-sidebar-width"), null);
    if (fromVar) return fromVar;
    if (assistantPanel) {
      const rect = assistantPanel.getBoundingClientRect();
      if (rect && rect.width) return rect.width;
    }
    return parseCssPx(readCssVar("--assistant-sidebar-min-width"), 360);
  };

  const historyEl = document.getElementById("llm-history");
  const historyContainerEl = document.getElementById("history-container");
  const scrollBottomBtn = document.getElementById("llm-scroll-bottom");
  let history = [];

  if (historyEl) {
    try {
      const parsedHistory = JSON.parse(historyEl.textContent || "[]");
      history = Array.isArray(parsedHistory) ? parsedHistory : [];
    } catch (error) {
      history = [];
    }
  }

  const chatStateEl = document.getElementById("llm-chat-state");
  const pinnedListEl = document.querySelector("[data-assistant-pinned-list]");
  const tempListEl = document.querySelector("[data-assistant-temp-list]");
  const pinnedEmptyEl = document.querySelector("[data-assistant-pinned-empty]");
  const tempEmptyEl = document.querySelector("[data-assistant-temp-empty]");
  const tempSectionEl = document.querySelector("[data-assistant-temp-section]");
  const historyErrorEl = document.querySelector("[data-assistant-history-error]");
  const assistantNewChatBtn = document.querySelector("[data-assistant-new-chat]");
  const chatDetailTemplate = assistantHistoryShell?.dataset.chatsDetailUrlTemplate || "";
  const chatPinTemplate = assistantHistoryShell?.dataset.chatsPinUrlTemplate || "";
  const chatNewUrl = assistantHistoryShell?.dataset.chatsNewUrl || "";

  const normalizeChatState = (state) => ({
    pinned_chats: Array.isArray(state?.pinned_chats) ? state.pinned_chats : [],
    temp_chat: state?.temp_chat || null,
    active_chat_id: state?.active_chat_id || null,
    max_pins: Number.isFinite(state?.max_pins) ? state.max_pins : 6,
  });

  let chatState = normalizeChatState({});
  if (chatStateEl) {
    try {
      chatState = normalizeChatState(JSON.parse(chatStateEl.textContent || "{}"));
    } catch (error) {
      chatState = normalizeChatState({});
    }
  }

  const showHistoryError = (message) => {
    if (!historyErrorEl) return;
    const text = String(message || "").trim();
    if (!text) {
      historyErrorEl.textContent = "";
      historyErrorEl.hidden = true;
      return;
    }
    historyErrorEl.textContent = text;
    historyErrorEl.hidden = false;
  };

  const buildChatDetailUrl = (chatId) =>
    chatDetailTemplate ? chatDetailTemplate.replace("0", String(chatId)) : "";
  const buildChatPinUrl = (chatId) =>
    chatPinTemplate ? chatPinTemplate.replace("0", String(chatId)) : "";

  const renderChatLists = () => {
    if (!pinnedListEl || !tempListEl) return;
    pinnedListEl.innerHTML = "";
    tempListEl.innerHTML = "";

    const pinnedChats = Array.isArray(chatState.pinned_chats)
      ? chatState.pinned_chats
      : [];
    const tempChat = chatState.temp_chat;

    pinnedChats.forEach((chat) => {
      const row = buildChatRow(chat, { isTemp: false });
      pinnedListEl.appendChild(row);
    });

    if (tempChat) {
      const row = buildChatRow(tempChat, { isTemp: true });
      tempListEl.appendChild(row);
    }

    if (pinnedEmptyEl) {
      pinnedEmptyEl.hidden = pinnedChats.length > 0;
    }
    if (tempEmptyEl) {
      tempEmptyEl.hidden = Boolean(tempChat);
    }
    if (tempSectionEl) {
      tempSectionEl.hidden = !tempChat;
    }
  };

  const buildChatRow = (chat, { isTemp }) => {
    const row = document.createElement("li");
    row.className = "assistant-history-row";

    const item = document.createElement("button");
    item.type = "button";
    item.className = "assistant-history-item";
    item.dataset.assistantChatId = String(chat.id);
    if (chatState.active_chat_id === chat.id) {
      item.classList.add("is-active");
    }

    const titleEl = document.createElement("span");
    titleEl.className = "assistant-history-item__title";
    titleEl.textContent = chat.title || "New chat";
    const metaEl = document.createElement("span");
    metaEl.className = "assistant-history-item__meta";
    metaEl.textContent = isTemp ? "Temporary" : "Pinned";

    item.appendChild(titleEl);
    item.appendChild(metaEl);

    const pinBtn = document.createElement("button");
    pinBtn.type = "button";
    pinBtn.className = "assistant-history-pin";
    pinBtn.dataset.assistantPinId = String(chat.id);
    pinBtn.setAttribute(
      "aria-label",
      chat.is_pinned ? "Unpin chat" : "Pin chat"
    );
    pinBtn.innerHTML = chat.is_pinned
      ? `
        <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true">
          <path d="M9 3h6l1.2 6.4-2.6 2.6v5.5l-2.6-1.8-2.6 1.8V12L7.8 9.4 9 3z"></path>
        </svg>
      `
      : `
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M9 3h6l1.2 6.4-2.6 2.6v5.5l-2.6-1.8-2.6 1.8V12L7.8 9.4 9 3z"></path>
        </svg>
      `;

    if (chat.is_pinned) {
      pinBtn.classList.add("is-pinned");
    }

    row.appendChild(item);
    row.appendChild(pinBtn);
    return row;
  };

  const applyChatState = (payload) => {
    if (!payload || !payload.chat_state) return;
    chatState = normalizeChatState(payload.chat_state);
    renderChatLists();
  };

  const getCsrfToken = () => {
    const input = document.querySelector(
      "#llm-form input[name='csrfmiddlewaretoken']"
    );
    if (input && input.value) return input.value;
    const cookie = document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
  };

  const requestChatPayload = async (url, options = {}) => {
    if (!url) throw new Error("Missing endpoint.");
    const response = await fetch(url, options);
    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      data = {};
    }
    if (!response.ok) {
      const message = data.error || "Request failed.";
      throw new Error(message);
    }
    return data;
  };

  const handleNewChat = async () => {
    showHistoryError("");
    setHistoryState(false);
    try {
      const data = await requestChatPayload(chatNewUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
      });
      if (Array.isArray(data.history)) {
        history = data.history;
        renderHistory();
      }
      applyChatState(data);
    } catch (error) {
      showHistoryError(error.message || "Unable to create chat.");
    }
  };

  const handleOpenChat = async (chatId) => {
    showHistoryError("");
    setHistoryState(false);
    const url = buildChatDetailUrl(chatId);
    try {
      const data = await requestChatPayload(url, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      });
      if (Array.isArray(data.history)) {
        history = data.history;
        renderHistory();
      }
      applyChatState(data);
    } catch (error) {
      showHistoryError(error.message || "Unable to open chat.");
    }
  };

  const handleTogglePin = async (chatId) => {
    showHistoryError("");
    const url = buildChatPinUrl(chatId);
    try {
      const data = await requestChatPayload(url, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
      });
      applyChatState(data);
    } catch (error) {
      showHistoryError(error.message || "Unable to pin chat.");
    }
  };
  const escapeHtml = (value) =>
    String(value).replace(/[&<>"']/g, (char) => {
      const map = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      };
      return map[char] || char;
    });

  const latexCommandPattern =
    /\\(frac|sqrt|Delta|alpha|beta|gamma|sigma|mu|lambda|approx|le|ge|neq|pm|times|div|cdot|rightarrow|leftarrow)/;

  const shouldAutoWrapLatex = (text) => {
    if (!text) return false;
    if (text.includes("$") || text.includes("\\(") || text.includes("\\[")) return false;
    if (!latexCommandPattern.test(text)) return false;
    const hasPlainWords = /(^|[^\\])([A-Za-z]{3,})/.test(text);
    return !hasPlainWords;
  };

  const isInsideIgnoredMathNode = (node) => {
    if (!node || !node.parentElement) return false;
    return Boolean(node.parentElement.closest("code, pre, .katex"));
  };

  const wrapBareLatexTextNodes = (root) => {
    if (!root || typeof document === "undefined") return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    let current = walker.nextNode();
    while (current) {
      const text = current.nodeValue || "";
      if (!isInsideIgnoredMathNode(current) && shouldAutoWrapLatex(text)) {
        current.nodeValue = `$${text}$`;
      }
      current = walker.nextNode();
    }
  };

  const renderChatMath = (container) => {
    if (!container || typeof renderMathInElement !== "function") return;
    const aiMessages = container.querySelectorAll(".llm-chat-row--ai .llm-chat-msg");
    aiMessages.forEach((messageEl) => wrapBareLatexTextNodes(messageEl));
    renderMathInElement(container, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true },
      ],
      throwOnError: false,
    });
  };

  const renderAssistantResponseMarkup = (item) => {
    const responseMode = item?.responseMode || "html";
    const responseText = String(item?.response || "");
    if (responseMode === "streaming") {
      return responseText
        ? escapeHtml(responseText).replace(/\n/g, "<br>")
        : waitingMarkup();
    }
    if (responseMode === "text") {
      return escapeHtml(responseText).replace(/\n/g, "<br>");
    }
    return responseText;
  };

  const waitingMarkup = () =>
    `
      <span class="llm-wait" role="status" aria-live="polite" aria-label="Assistant is thinking">
        <span class="llm-wait__dot"></span>
        <span class="llm-wait__dot"></span>
        <span class="llm-wait__dot"></span>
      </span>
    `.trim();

  const copyIconMarkup = window.copyUtils && window.copyUtils.copyIconMarkup
    ? window.copyUtils.copyIconMarkup
    : "";

  const isHistoryNearBottom = (container, threshold = 14) => {
    if (!container) return true;
    return container.scrollTop + container.clientHeight >= container.scrollHeight - threshold;
  };

  const updateScrollBottomVisibility = () => {
    if (!historyContainerEl || !scrollBottomBtn) return;
    const hasOverflow = historyContainerEl.scrollHeight > historyContainerEl.clientHeight + 2;
    const shouldShow = hasOverflow && !isHistoryNearBottom(historyContainerEl);
    scrollBottomBtn.hidden = !shouldShow;
    scrollBottomBtn.classList.toggle("is-visible", shouldShow);
  };

  let assistantCopyOverlay = null;
  const ensureAssistantCopyOverlay = () => {
    if (!historyContainerEl) return;
    if (!window.copyUtils || typeof window.copyUtils.registerCodeCopyOverlay !== "function") return;
    if (assistantCopyOverlay) return;
    assistantCopyOverlay = window.copyUtils.registerCodeCopyOverlay({
      root: historyContainerEl,
      host: historyContainerEl,
      scrollContainer: historyContainerEl,
      codeSelector: ".llm-chat-row--ai .llm-chat-msg pre",
      offsetX: 8,
      offsetY: 8,
    });
  };

  const handleViewportChange = () => {
    if (desktopMediaQuery && !desktopMediaQuery.matches) {
      bodyEl.classList.remove("assistant-resizing");
      if (assistantPanel) {
        assistantPanel.style.left = "";
        assistantPanel.style.top = "";
        assistantPanel.style.width = "";
        assistantPanel.style.height = "";
        assistantPanel.style.right = "";
      }
      return;
    }
    if (bodyEl.classList.contains("assistant-sidebar-open")) {
      clampSidebarPosition();
    } else {
      restoreAssistantSidebarDimensions();
    }
  };

  const setupResizeHandle = () => {
    if (!assistantPanel) return;
    const handles = assistantPanel.querySelectorAll("[data-resize-edge]");
    
    handles.forEach((handle) => {
      const edge = handle.dataset.resizeEdge;
      
      let startX = 0;
      let startY = 0;
      let startWidth = 0;
      let startHeight = 0;
      let startLeft = 0;
      let startTop = 0;
      let activePointerId = null;

      const startResize = (event) => {
        if (event.button !== 0) return;
        if (!bodyEl.classList.contains("assistant-sidebar-open")) return;
        if (desktopMediaQuery && !desktopMediaQuery.matches) return;

        event.preventDefault();
        activePointerId = event.pointerId;
        startX = event.clientX;
        startY = event.clientY;

        const rect = assistantPanel.getBoundingClientRect();
        startWidth = rect.width;
        startHeight = rect.height;
        startLeft = parseFloat(assistantPanel.style.left) || rect.left;
        startTop = parseFloat(assistantPanel.style.top) || rect.top;

        bodyEl.classList.add("assistant-resizing");

        if (handle.setPointerCapture) {
          handle.setPointerCapture(event.pointerId);
        }

        window.addEventListener("pointermove", onPointerMove);
        window.addEventListener("pointerup", stopResize);
        window.addEventListener("pointercancel", stopResize);
      };

      const onPointerMove = (event) => {
        if (activePointerId === null) return;
        
        const deltaX = event.clientX - startX;
        const deltaY = event.clientY - startY;

        const minWidth = 360;
        const maxWidth = 760;
        const minHeight = 300;
        const maxHeight = window.innerHeight - 80;

        if (edge === "right") {
          const newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth + deltaX));
          assistantPanel.style.width = `${newWidth}px`;
        } 
        else if (edge === "left") {
          const newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth - deltaX));
          if (newWidth !== minWidth && newWidth !== maxWidth) {
            assistantPanel.style.width = `${newWidth}px`;
            assistantPanel.style.left = `${startLeft + deltaX}px`;
            assistantPanel.style.right = "auto";
          }
        } 
        else if (edge === "bottom") {
          const newHeight = Math.max(minHeight, Math.min(maxHeight, startHeight + deltaY));
          assistantPanel.style.height = `${newHeight}px`;
        } 
        else if (edge === "top") {
          const newHeight = Math.max(minHeight, Math.min(maxHeight, startHeight - deltaY));
          if (newHeight !== minHeight && newHeight !== maxHeight) {
            assistantPanel.style.height = `${newHeight}px`;
            assistantPanel.style.top = `${startTop + deltaY}px`;
          }
        }
      };

      const stopResize = () => {
        if (activePointerId === null) return;
        if (handle.releasePointerCapture) {
          handle.releasePointerCapture(activePointerId);
        }
        activePointerId = null;
        bodyEl.classList.remove("assistant-resizing");
        window.removeEventListener("pointermove", onPointerMove);
        window.removeEventListener("pointerup", stopResize);
        window.removeEventListener("pointercancel", stopResize);

        try {
          localStorage.setItem("assistant_float_width", assistantPanel.style.width);
          localStorage.setItem("assistant_float_height", assistantPanel.style.height);
          localStorage.setItem("assistant_float_left", assistantPanel.style.left);
          localStorage.setItem("assistant_float_top", assistantPanel.style.top);
        } catch (e) {}
      };

      handle.addEventListener("pointerdown", startResize);
    });
  };

  const setupDragAndDrop = () => {
    if (!assistantPanel) return;
    const toolbar = assistantPanel.querySelector(".assistance-toolbar");
    if (!toolbar) return;

    let startX = 0;
    let startY = 0;
    let startLeft = 0;
    let startTop = 0;
    let isDragging = false;

    const onPointerDown = (event) => {
      if (event.button !== 0) return;
      if (desktopMediaQuery && !desktopMediaQuery.matches) return;
      if (event.target.closest("button, input, select, textarea, a")) return;

      event.preventDefault();
      isDragging = true;
      startX = event.clientX;
      startY = event.clientY;
      startLeft = parseFloat(assistantPanel.style.left) || assistantPanel.offsetLeft || 0;
      startTop = parseFloat(assistantPanel.style.top) || assistantPanel.offsetTop || 0;

      bodyEl.classList.add("assistant-dragging");

      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", onPointerUp);
      window.addEventListener("pointercancel", onPointerUp);
    };

    const onPointerMove = (event) => {
      if (!isDragging) return;
      const deltaX = event.clientX - startX;
      const deltaY = event.clientY - startY;

      let nextLeft = startLeft + deltaX;
      let nextTop = startTop + deltaY;

      nextLeft = Math.max(16, Math.min(window.innerWidth - assistantPanel.offsetWidth - 16, nextLeft));
      nextTop = Math.max(16, Math.min(window.innerHeight - assistantPanel.offsetHeight - 16, nextTop));

      assistantPanel.style.left = `${nextLeft}px`;
      assistantPanel.style.top = `${nextTop}px`;
      assistantPanel.style.right = "auto";
    };

    const onPointerUp = () => {
      if (!isDragging) return;
      isDragging = false;
      bodyEl.classList.remove("assistant-dragging");
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);

      try {
        localStorage.setItem("assistant_float_left", assistantPanel.style.left);
        localStorage.setItem("assistant_float_top", assistantPanel.style.top);
      } catch (e) {}
    };

    toolbar.addEventListener("pointerdown", onPointerDown);
  };

  document.addEventListener("keydown", function (event) {
    const isToggleShortcut =
      (event.ctrlKey || event.metaKey) &&
      !event.altKey &&
      !event.shiftKey &&
      String(event.key).toLowerCase() === "b";

    if (!isToggleShortcut) return;
    // Allow toggle inside the assistant prompt itself so Ctrl/Cmd+B can also close.
    if (isEditableTarget(event.target) && event.target?.id !== "id_prompt") return;
    // Prevent browser default (for example bookmarks toggle) and handle sidebar toggle.
    event.preventDefault();
    toggleAssistantSidebar();
  });

  if (assistantPanel) {
    updateAssistantOffset();
    const handleWindowResize = () => {
      updateAssistantOffset();
      handleViewportChange();
    };
    window.addEventListener("resize", handleWindowResize);

    //if (assistantHideBtn) {
    //  assistantHideBtn.addEventListener("click", hideAssistant);
    //}
    if (assistantCloseBtn) {
      assistantCloseBtn.addEventListener("click", hideAssistant);
    }
    if (assistantHistoryToggle) {
      assistantHistoryToggle.addEventListener("click", () => {
        const isOpen = assistantPanel.classList.contains("assistant-history-open");
        setHistoryState(!isOpen);
      });
    }
    if (assistantLauncher) {
      assistantLauncher.addEventListener("click", () => {
        openAssistantSidebar();
        focusAssistantPrompt();
      });
    }

    setupResizeHandle();
    setupDragAndDrop();

    const initialState = readAssistantState();
    setAssistantState(initialState, { persist: false });
    setHistoryState(readHistoryState(), { persist: false });
    handleViewportChange();

    if (desktopMediaQuery) {
      if (typeof desktopMediaQuery.addEventListener === "function") {
        desktopMediaQuery.addEventListener("change", handleViewportChange);
      } else if (typeof desktopMediaQuery.addListener === "function") {
        desktopMediaQuery.addListener(handleViewportChange);
      }
    }
  }

const enhanceChatTables = (container) => {
  if (!container) return;

  container.querySelectorAll(".llm-chat-row--ai .llm-chat-msg table").forEach((table) => {
    table.classList.add("llm-chat-table");

    if (!table.parentElement || !table.parentElement.classList.contains("llm-chat-table-wrap")) {
      // Wrap each table to enable horizontal scrolling without shrinking text size.
      const wrap = document.createElement("div");
      wrap.className = "llm-chat-table-wrap";
      table.parentNode.insertBefore(wrap, table);
      wrap.appendChild(table);
    }

    // Collect header labels for stacked mobile fallback.
    let headerCells = Array.from(table.querySelectorAll("thead tr:first-child th"));
    if (!headerCells.length) {
      const firstRow = table.querySelector("tr");
      if (firstRow) {
        headerCells = Array.from(firstRow.children);
      }
    }

    const headerLabels = headerCells.map((cell, index) => {
      const text = (cell.textContent || "").trim();
      return text || `Column ${index + 1}`;
    });

    let dataRows = Array.from(table.querySelectorAll("tbody tr"));
    if (!dataRows.length) {
      const rows = Array.from(table.querySelectorAll("tr"));
      dataRows = rows.slice(headerCells.length ? 1 : 0);
    }

    dataRows.forEach((row) => {
      Array.from(row.children).forEach((cell, index) => {
        if (cell.tagName !== "TD") return;
        cell.setAttribute("data-label", headerLabels[index] || `Column ${index + 1}`);
      });
    });
  });
};

if (historyContainerEl) {
  historyContainerEl.addEventListener("scroll", updateScrollBottomVisibility, { passive: true });
  ensureAssistantCopyOverlay();
}

if (scrollBottomBtn && historyContainerEl) {
  scrollBottomBtn.addEventListener("click", function () {
    historyContainerEl.scrollTo({
      top: historyContainerEl.scrollHeight,
      behavior: "smooth",
    });
    // Recheck visibility once smooth scroll settles.
    window.setTimeout(updateScrollBottomVisibility, 220);
  });
}

window.addEventListener("resize", updateScrollBottomVisibility);


function renderHistory() {
  const container = historyContainerEl;
  if (!container) return;

  const wasNearBottom = isHistoryNearBottom(container);
  const previousScrollTop = container.scrollTop;

  container.innerHTML = "";
  history.forEach((item, itemIndex) => {
    const isPendingResponse =
      (item.responseMode === "streaming" && !String(item.response || "").trim()) ||
      (typeof item.response === "string" && item.response.includes("llm-wait__dot"));
    const responseMarkup = renderAssistantResponseMarkup(item);
    const entry = document.createElement("div");
    entry.className = "llm-chat-entry";
    entry.innerHTML = `
      <div class="llm-chat-row llm-chat-row--user">
        <div class="llm-chat-stack llm-chat-stack--user">
          <div class="llm-chat-bubble llm-chat-bubble--user">
            <div class="llm-chat-msg">${escapeHtml(item.prompt)}</div>
          </div>
          <div class="llm-chat-bubble__actions llm-chat-bubble__actions--outside">
            <button
              class="llm-copy-btn llm-copy-message"
              type="button"
              aria-label="Copy prompt"
              title="Copy prompt"
              data-copy-scope="prompt"
              data-copy-default="Copy prompt"
              data-copy-copied="Copied"
              data-copy-failed="Failed"
            >
              ${copyIconMarkup}
            </button>
          </div>
        </div>
      </div>
      <div class="llm-chat-row llm-chat-row--ai">
        <div class="llm-chat-bubble llm-chat-bubble--ai">
          <div class="llm-chat-msg">${responseMarkup}</div>
          <div class="llm-chat-bubble__actions">
            <button
              class="llm-copy-btn llm-copy-message"
              type="button"
              aria-label="Copy response"
              title="Copy response"
              data-copy-scope="response"
              data-response-index="${itemIndex}"
              data-copy-default="Copy response"
              data-copy-copied="Copied"
              data-copy-failed="Failed"
              ${isPendingResponse ? "disabled aria-disabled='true'" : ""}
            >
              ${copyIconMarkup}
            </button>
          </div>
        </div>
      </div>
    `;
    container.appendChild(entry);
  });

  // Render LaTeX after messages are added to the DOM.
  renderChatMath(container);
  // Normalize AI tables after each render so layout stays responsive.
  enhanceChatTables(container);
  ensureAssistantCopyOverlay();
  if (window.copyUtils && typeof window.copyUtils.refreshCodeCopyOverlays === "function") {
    window.copyUtils.refreshCodeCopyOverlays();
  }

  if (wasNearBottom) {
    container.scrollTop = container.scrollHeight;
  } else {
    container.scrollTop = Math.min(
      previousScrollTop,
      Math.max(0, container.scrollHeight - container.clientHeight)
    );
  }
  highlightGeneratedCode(container);
  updateScrollBottomVisibility();

}
 // llm code highlight
  const highlightGeneratedCode = (container) => {
  if (!container || !window.hljs) return;
  container
    .querySelectorAll(".llm-chat-row--ai .llm-chat-msg pre code")
    .forEach((block) => hljs.highlightElement(block));
};


  renderHistory();
  renderChatLists();
  window.addEventListener("load", () => {
    renderChatMath(historyContainerEl);
  });
  if (assistantHistorySidebar) {
    assistantHistorySidebar.addEventListener("click", (event) => {
      const pinBtn = event.target.closest("[data-assistant-pin-id]");
      if (pinBtn) {
        event.preventDefault();
        handleTogglePin(pinBtn.dataset.assistantPinId);
        return;
      }
      const chatBtn = event.target.closest("[data-assistant-chat-id]");
      if (chatBtn) {
        event.preventDefault();
        handleOpenChat(chatBtn.dataset.assistantChatId);
      }
    });
  }
  if (assistantNewChatBtn) {
    assistantNewChatBtn.addEventListener("click", handleNewChat);
  }
  const form = document.getElementById("llm-form");
  const promptInput = document.getElementById("id_prompt");
  if (form && promptInput) {
    const composer = form.querySelector(".llm-composer");
    const sendBtn = form.querySelector('button[type="submit"]');
    const csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
    const csrfToken = csrfInput ? csrfInput.value : "";
    const maxInputHeight = 64;
    let isSubmitting = false;
    let activeRequestController = null;

    const setSendButtonMode = (mode) => {
      if (!sendBtn) return;
      const isStopMode = mode === "stop";
      // While generating, the same button becomes an explicit stop control.
      sendBtn.classList.toggle("is-stop", isStopMode);
      sendBtn.setAttribute("aria-label", isStopMode ? "Stop response" : "Send message");
      sendBtn.setAttribute("title", isStopMode ? "Stop response" : "Send message");
    };

    const abortCurrentResponse = () => {
      if (!isSubmitting || !activeRequestController) return false;
      activeRequestController.abort();
      return true;
    };

    const syncComposerState = () => {
      if (!composer) return;
      composer.classList.toggle("is-active", document.activeElement === promptInput);
    };

    const autoGrow = () => {
      promptInput.style.height = "auto";
      const next = Math.min(promptInput.scrollHeight, maxInputHeight);
      promptInput.style.height = `${next}px`;
      promptInput.style.overflowY =
        promptInput.scrollHeight > maxInputHeight ? "auto" : "hidden";
    };

    autoGrow();
  syncComposerState();
    setSendButtonMode("send");

    if (sendBtn) {
      sendBtn.addEventListener("click", (event) => {
        if (!isSubmitting) return;
        // Stop is click-only by requirement; Enter key does not trigger cancellation.
        event.preventDefault();
        event.stopPropagation();
        abortCurrentResponse();
      });
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      // Single-flight guard: block both button and Enter resubmits while awaiting AI response.
      if (isSubmitting || (sendBtn && sendBtn.disabled)) return;
      const prompt = promptInput.value.trim();
      if (!prompt) return;

      isSubmitting = true;
      promptInput.value = "";
      autoGrow();
      openAssistantSidebar();
      setSendButtonMode("stop");
      activeRequestController = new AbortController();
      const activeItem = {
        prompt: prompt,
        response: "",
        responseMode: "streaming",
      };
      history.push(activeItem);
      renderHistory();

      try {
        const response = await fetch((assistantPanel ? (assistantPanel.dataset.generateUrl || "") : ""), {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": csrfToken,
          },
          credentials: "same-origin",
          signal: activeRequestController.signal,
          body: new URLSearchParams({ prompt: prompt }),
        });

        if (!response.ok) {
          let data = {};
          try {
            data = await response.json();
          } catch (err) {
            data = {};
          }
          const detailMessage =
            data.details && (data.details.message || data.details.error);
          const message = detailMessage
            ? `${data.error || "Request failed."} (${detailMessage})`
            : data.error || `Request failed (${response.status}).`;
          activeItem.response = message;
          activeItem.responseMode = "text";
          renderHistory();
          applyChatState(data);
        } else {
          const data = await response.json();

          if (data && data.error) {
            activeItem.response = String(data.error || "Request failed.");
            activeItem.responseMode = "text";
          } else {
            activeItem.response = String(data.generated || "");
            activeItem.responseMode = "html";
          }

          renderHistory();
          applyChatState(data);
        }
      } catch (error) {
        if (error && error.name === "AbortError") {
          activeItem.response = "Response stopped.";
          activeItem.responseMode = "text";
        } else {
          activeItem.response = error?.message || "Network error. Please try again.";
          activeItem.responseMode = "text";
        }
        renderHistory();
      } finally {
        activeRequestController = null;
        isSubmitting = false;
        setSendButtonMode("send");
        promptInput.focus();
      }
    });

    promptInput.addEventListener("input", autoGrow);
    promptInput.addEventListener("focus", syncComposerState);
    promptInput.addEventListener("blur", syncComposerState);

    promptInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (isSubmitting || (sendBtn && sendBtn.disabled)) return;
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit(sendBtn || undefined);
        } else {
          form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
        }
      }
    });
  }
