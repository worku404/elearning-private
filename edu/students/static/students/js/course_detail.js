// Extracted from students/course/detail.html
// Django URLs are supplied via data-complete-url, data-time-url, data-module-id
// on the outermost <section> wrapper of the course detail page.
window.addEventListener("pageshow", function (event) {
    if (event.persisted) window.location.reload();
});

let startTime = Date.now();
let completionSent = false;
let userHasScrolled = false;
let timeHeartbeatId = null;
const modulesUiStateKey = "modules_sidebar_state";

const moduleContainer = document.querySelector(".module");
const _shell         = document.querySelector("[data-complete-url]");
const completeUrl    = _shell ? (_shell.dataset.completeUrl || "") : "";
const timeUrl        = _shell ? (_shell.dataset.timeUrl     || "") : "";
const activeModuleId = Number(_shell ? (_shell.dataset.moduleId || "0") : "0") || null;
const workspaceEl = document.querySelector(".course-workspace");
const moduleSidebarEl = document.getElementById("module-sidebar");
const courseProgressWrapEl = document.querySelector("[data-course-progress]");
const courseProgressBarEl = document.querySelector("[data-course-progress-bar]");
const courseProgressValueEl = document.querySelector("[data-course-progress-value]");
const textTrackElements = Array.from(document.querySelectorAll(".js-track-text"));
const pdfViewerElements = Array.from(document.querySelectorAll(".js-pdf-viewer"));
const videoTrackElements = Array.from(document.querySelectorAll(".js-track-video"))
    .map((wrapper) => {
        if (!wrapper) return null;
        const video = wrapper.querySelector("video");
        if (!video) return null;
        const contentId = wrapper.dataset.contentId;
        const progressUrl = wrapper.dataset.progressUrl;
        const resumeTime = Number(wrapper.dataset.resumeTime || 0);
        if (!contentId || !progressUrl) return null;
        return { wrapper, video, contentId, progressUrl, resumeTime, resumeApplied: false };
    })
    .filter(Boolean);
const hasTrackableContent = textTrackElements.length > 0
    || pdfViewerElements.length > 0
    || videoTrackElements.length > 0;
const contentProgressState = new Map();
const contentCompletionThreshold = 95;
let pdfLayoutRefreshTimeoutId = null;

function persistModulesState(state) {
    try { localStorage.setItem(modulesUiStateKey, state); } catch (e) {}
}

function applyModulesCollapsed(collapsed) {
    if (!workspaceEl || !moduleSidebarEl) return;
    workspaceEl.classList.toggle("modules-collapsed", collapsed);
    document.body.classList.toggle("modules-sidebar-collapsed", collapsed);
    moduleSidebarEl.setAttribute("aria-hidden", String(collapsed));
}

function schedulePdfLayoutRefresh() {
    if (!window.PdfViewer) return;
    if (pdfLayoutRefreshTimeoutId !== null) window.clearTimeout(pdfLayoutRefreshTimeoutId);
    pdfLayoutRefreshTimeoutId = window.setTimeout(() => {
        pdfLayoutRefreshTimeoutId = null;
        if (!window.PdfViewer) return;
        if (typeof window.PdfViewer.setAutoZoomAll === "function") window.PdfViewer.setAutoZoomAll();
        if (typeof window.PdfViewer.refreshAll === "function") window.PdfViewer.refreshAll();
    }, 240);
}

if (workspaceEl && moduleSidebarEl) {
    let storedState = "expanded";
    try { storedState = localStorage.getItem(modulesUiStateKey) || "expanded"; } catch (e) {}
    applyModulesCollapsed(storedState === "collapsed");
}

window.setModulesCollapsed = function (collapsed) {
    applyModulesCollapsed(Boolean(collapsed));
    persistModulesState(collapsed ? "collapsed" : "expanded");
};
window.toggleModulesCollapsed = function () {
    window.setModulesCollapsed(!document.body.classList.contains("modules-sidebar-collapsed"));
};

window.addEventListener("keydown", function (event) {
    if (!event.ctrlKey || !event.shiftKey || event.code !== "KeyX") return;
    const tag = (event.target?.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select" || event.target?.isContentEditable) return;
    event.preventDefault();
    window.toggleModulesCollapsed();
});

function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split("; ") : [];
    for (const c of cookies) {
        const [key, ...rest] = c.split("=");
        if (key === name) return decodeURIComponent(rest.join("="));
    }
    return "";
}

function clampPercent(value) {
    return Math.max(0, Math.min(100, Number(value) || 0));
}

function getStateForContent(contentId) {
    const key = String(contentId || "");
    if (!contentProgressState.has(key)) {
        contentProgressState.set(key, { highestPercent: 0, lastSentPercent: 0, lastSentAt: Date.now() });
    }
    return contentProgressState.get(key);
}

function trackVideoProgress(entry, force = false) {
    if (!entry || !entry.video) return;
    const duration = Number(entry.video.duration || 0);
    if (!duration || !Number.isFinite(duration)) return;
    const currentTime = Number(entry.video.currentTime || 0);
    const state = getStateForContent(entry.contentId);
    const maxTimeSeen = Math.max(Number(state.maxTimeSeen || 0), currentTime, 0);
    state.maxTimeSeen = maxTimeSeen;
    const computedPercent = clampPercent((maxTimeSeen / duration) * 100);
    state.highestPercent = Math.max(Number(state.highestPercent || 0), computedPercent);
    const shouldSend = force
        || state.highestPercent >= contentCompletionThreshold
        || (state.highestPercent - state.lastSentPercent) >= 2;
    if (!shouldSend) return;
    const secondsDelta = Math.max(0, Math.floor(maxTimeSeen - Number(state.lastSentMediaTime || 0)));
    state.lastSentMediaTime = Math.max(Number(state.lastSentMediaTime || 0), maxTimeSeen);
    state.lastSentAt = Date.now();
    state.lastSentPercent = state.highestPercent;
    postContentProgress(entry.progressUrl, {
        kind: "video",
        duration: Number(duration.toFixed(3)),
        current_time: Number(currentTime.toFixed(3)),
        max_time_seen: Number(maxTimeSeen.toFixed(3)),
        percent: Number(state.highestPercent.toFixed(2)),
        seconds_delta: secondsDelta,
    });
}

function trackAllVideos(force = false) {
    videoTrackElements.forEach((entry) => trackVideoProgress(entry, force));
}

videoTrackElements.forEach((entry) => {
    const video = entry.video;
    if (!video) return;
    video.addEventListener("loadedmetadata", function () {
        if (!entry.resumeApplied) {
            const duration = Number(video.duration || 0);
            const resumeTime = Number(entry.resumeTime || 0);
            if (duration && Number.isFinite(duration) && resumeTime > 0) {
                const safeTime = Math.min(resumeTime, Math.max(0, duration - 0.5));
                if (safeTime > 0) video.currentTime = safeTime;
            }
            entry.resumeApplied = true;
        }
        trackVideoProgress(entry, true);
    });
    video.addEventListener("timeupdate", () => trackVideoProgress(entry, false));
    video.addEventListener("pause",       () => trackVideoProgress(entry, true));
    video.addEventListener("ended", function () {
        const duration = Number(video.duration || 0);
        if (duration && Number.isFinite(duration)) {
            const state = getStateForContent(entry.contentId);
            state.maxTimeSeen = Math.max(Number(state.maxTimeSeen || 0), duration);
            state.highestPercent = 100;
        }
        trackVideoProgress(entry, true);
    });
});

function updateModuleProgressUI(moduleId, percent) {
    const normalizedModuleId = Number(moduleId || 0);
    if (!normalizedModuleId) return;
    const moduleRow = document.querySelector(`[data-module-id="${normalizedModuleId}"]`);
    if (!moduleRow) return;
    const normalizedPercent = clampPercent(percent);
    const roundedPercent = Math.round(normalizedPercent);
    const progressWrap  = moduleRow.querySelector("[data-module-progress]");
    const progressBar   = moduleRow.querySelector("[data-module-progress-bar]");
    const progressBadge = moduleRow.querySelector("[data-module-progress-badge]");
    const progressBadgeLabel = moduleRow.querySelector("[data-module-progress-badge-label]");
    if (progressWrap)  progressWrap.setAttribute("aria-valuenow", String(roundedPercent));
    if (progressBar)   progressBar.style.width = `${normalizedPercent}%`;
    if (progressBadge) {
        progressBadge.style.setProperty("--pdf-progress", `${normalizedPercent}%`);
        progressBadge.setAttribute("aria-valuenow", String(roundedPercent));
        progressBadge.classList.toggle("is-complete", normalizedPercent >= 100);
    }
    if (progressBadgeLabel) {
        progressBadgeLabel.textContent = normalizedPercent >= 100
            ? "\u2714" : `${Math.min(99, roundedPercent)}%`;
    }
}

function updateCourseProgressUI(percent) {
    const normalizedPercent = clampPercent(percent);
    const roundedPercent = Math.round(normalizedPercent);
    if (courseProgressWrapEl)  courseProgressWrapEl.setAttribute("aria-valuenow", String(roundedPercent));
    if (courseProgressBarEl)   courseProgressBarEl.style.width = `${normalizedPercent}%`;
    if (courseProgressValueEl) courseProgressValueEl.textContent = String(roundedPercent);
}

function applyProgressPayload(payload) {
    if (!payload || typeof payload !== "object") return;
    const moduleProgress = payload.module_progress || null;
    if (moduleProgress && moduleProgress.module_id) {
        updateModuleProgressUI(moduleProgress.module_id, moduleProgress.progress_percent);
    } else if (activeModuleId && payload.status === "completed") {
        updateModuleProgressUI(activeModuleId, 100);
    }
    const courseProgress = payload.course_progress || null;
    if (courseProgress) updateCourseProgressUI(courseProgress.progress_percent);
}

function postContentProgress(progressUrl, payload, options = {}) {
    if (!progressUrl) return Promise.resolve(null);
    return fetch(progressUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
            "X-Requested-With": "XMLHttpRequest"
        },
        credentials: "same-origin",
        keepalive: Boolean(options.keepalive),
        body: JSON.stringify(payload),
    })
        .then((r) => (r.ok ? r.json().catch(() => null) : null))
        .then((data) => { applyProgressPayload(data); return data; })
        .catch(() => null);
}

function computeTextProgress(el) {
    if (!el) return 0;
    const rect = el.getBoundingClientRect();
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 1;
    if (rect.height <= 1) return 0;
    const visiblePx = Math.max(0, Math.min(rect.bottom, viewportHeight) - Math.max(rect.top, 0));
    const visibilityRatio = visiblePx / rect.height;
    const topInDoc = rect.top + window.scrollY;
    const depthRatio = (window.scrollY + viewportHeight - topInDoc) / rect.height;
    return clampPercent(Math.max(visibilityRatio, depthRatio) * 100);
}

function trackVisibleText(force = false) {
    const now = Date.now();
    textTrackElements.forEach((el) => {
        const contentId   = el.dataset.contentId;
        const progressUrl = el.dataset.progressUrl;
        if (!contentId || !progressUrl) return;
        const state = getStateForContent(contentId);
        state.highestPercent = Math.max(state.highestPercent, computeTextProgress(el));
        const shouldSend = force
            || state.highestPercent >= contentCompletionThreshold
            || (state.highestPercent - state.lastSentPercent) >= 4;
        if (!shouldSend) return;
        const secondsDelta = Math.max(0, Math.floor((now - state.lastSentAt) / 1000));
        state.lastSentAt = now;
        state.lastSentPercent = state.highestPercent;
        postContentProgress(progressUrl, {
            kind: "text",
            percent: Number(state.highestPercent.toFixed(2)),
            seconds_delta: secondsDelta,
        });
    });
}

function isAtBottom() {
    if (moduleContainer && moduleContainer.scrollHeight > moduleContainer.clientHeight + 2) {
        return moduleContainer.scrollTop + moduleContainer.clientHeight >= moduleContainer.scrollHeight - 8;
    }
    return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 8;
}

function markCompleteIfNeeded() {
    if (hasTrackableContent) return;
    if (!completeUrl || completionSent || !userHasScrolled || !isAtBottom()) return;
    completionSent = true;
    fetch(completeUrl, {
        method: "POST",
        headers: { "X-CSRFToken": getCookie("csrftoken"), "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin"
    })
        .then((r) => (r.ok ? r.json().catch(() => null) : null))
        .then((data) => { applyProgressPayload(data); })
        .catch(() => { completionSent = false; });
}

function onScroll() {
    userHasScrolled = true;
    markCompleteIfNeeded();
    trackVisibleText(false);
}
window.addEventListener("scroll", onScroll, { passive: true });
if (moduleContainer) moduleContainer.addEventListener("scroll", onScroll, { passive: true });

document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
        stopTimeHeartbeat(); sendTime(); trackVisibleText(true); trackAllVideos(true);
        if (window.PdfViewer) window.PdfViewer.flushAll();
    } else {
        startTime = Date.now(); startTimeHeartbeat();
    }
});

function sendTime() {
    const seconds = Math.floor((Date.now() - startTime) / 1000);
    if (seconds <= 0 || !timeUrl) return;
    const formData = new FormData();
    formData.append("seconds", seconds);
    formData.append("csrfmiddlewaretoken", getCookie("csrftoken"));
    navigator.sendBeacon(timeUrl, formData);
    startTime = Date.now();
}
function startTimeHeartbeat() {
    if (!timeUrl || timeHeartbeatId !== null) return;
    timeHeartbeatId = window.setInterval(sendTime, 60000);
}
function stopTimeHeartbeat() {
    if (timeHeartbeatId === null) return;
    window.clearInterval(timeHeartbeatId);
    timeHeartbeatId = null;
}
startTimeHeartbeat();

window.addEventListener("beforeunload", function () { stopTimeHeartbeat(); sendTime(); });
window.addEventListener("beforeunload", function () {
    trackVisibleText(true); trackAllVideos(true);
    if (window.PdfViewer) window.PdfViewer.flushAll();
});
window.addEventListener("resize", function () {
    trackVisibleText(false);
    if (window.PdfViewer) window.PdfViewer.refreshAll();
}, { passive: true });

const searchParams    = new URLSearchParams(window.location.search);
const targetContentId = Number(searchParams.get("content_id") || 0);
const searchQuery     = (searchParams.get("q") || "").trim();
const targetPage      = Number(searchParams.get("page") || 0);
const targetContentEl = targetContentId
    ? document.querySelector(`[data-content-id="${targetContentId}"]`) : null;

if (targetContentEl && targetPage) {
    const pdfViewer = targetContentEl.querySelector(".js-pdf-viewer");
    if (pdfViewer) {
        pdfViewer.dataset.startPage   = String(targetPage);
        pdfViewer.dataset.maxPageSeen = String(targetPage);
    }
}

function escapeSearchRegExp(value) {
    return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightMatchesInElement(root, query) {
    if (!root || !query) return;
    const normalized = String(query || "").trim();
    if (!normalized) return;
    const regex = new RegExp(escapeSearchRegExp(normalized), "gi");
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode: (node) => {
            if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
            const parent = node.parentElement;
            if (!parent) return NodeFilter.FILTER_REJECT;
            if (parent.closest("script, style, mark, pre, code")) return NodeFilter.FILTER_REJECT;
            return NodeFilter.FILTER_ACCEPT;
        },
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((textNode) => {
        const text = textNode.nodeValue;
        if (!regex.test(text)) return;
        regex.lastIndex = 0;
        const fragment = document.createDocumentFragment();
        let lastIndex = 0;
        text.replace(regex, (match, offset) => {
            if (offset > lastIndex) fragment.appendChild(document.createTextNode(text.slice(lastIndex, offset)));
            const mark = document.createElement("mark");
            mark.className = "search-highlight";
            mark.textContent = match;
            fragment.appendChild(mark);
            lastIndex = offset + match.length;
        });
        if (lastIndex < text.length) fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
        textNode.parentNode.replaceChild(fragment, textNode);
    });
}

function applySearchTarget() {
    if (!targetContentEl) return;
    targetContentEl.classList.add("is-search-target");
    targetContentEl.scrollIntoView({ behavior: "smooth", block: "start" });
    if (searchQuery) {
        const renderEl = targetContentEl.querySelector(".c-content-render") || targetContentEl;
        highlightMatchesInElement(renderEl, searchQuery);
        const firstMark = renderEl.querySelector("mark.search-highlight");
        if (firstMark) firstMark.scrollIntoView({ behavior: "smooth", block: "center" });
    }
}

// ── Code runner ────────────────────────────────────────────────────────────────

// Maps every class name hljs or the markdown renderer might put on <code>
// to the language string our Django endpoint expects.
const RUNNABLE_LANGUAGES = {
    "python": "python", "py": "python", "python3": "python",
    "language-python": "python", "language-py": "python",
    "javascript": "javascript", "js": "javascript",
    "language-javascript": "javascript", "language-js": "javascript",
    "c++": "c++", "cpp": "c++",
    "language-c++": "c++", "language-cpp": "c++",
    "sql": "sqlite3", "sqlite": "sqlite3", "sqlite3": "sqlite3",
    "language-sql": "sqlite3", "language-sqlite": "sqlite3", "language-sqlite3": "sqlite3",
};

const LANG_LABELS = { python: "Python", javascript: "JavaScript", "c++": "C++" , sqlite3: "SQL"};

function detectRunLanguage(codeEl) {
    if (!codeEl) return null;

    // First detect the language from class names (existing logic)
    let lang = null;
    for (const cls of codeEl.classList) {
        const detected = RUNNABLE_LANGUAGES[cls.toLowerCase().trim()];
        if (detected) { lang = detected; break; }
    }
    if (!lang) return null;

    // Then check if the code has something worth running
    const code = (codeEl.textContent || "").trim();
    if (!code) return null;

    if (lang === "python") {
        // Show run button only if there's a print() call or visible output
        const hasPrint = /\bprint\s*\(/.test(code);
        return hasPrint ? lang : null;
    }

    if (lang === "javascript") {
        // Show run button only if there's console.log or document.write
        const hasOutput = /\bconsole\s*\.\s*log\s*\(/.test(code)
            || /\bdocument\s*\.\s*write\s*\(/.test(code);
        return hasOutput ? lang : null;
    }

    if (lang === "c++") {
        // Show run button only if there's a main() function
        const hasMain = /\bint\s+main\s*\(/.test(code);
        return hasMain ? lang : null;
    }

    if (lang === "sqlite3") {
        // Always show for SQL — SELECT is the "output" indicator
        const hasSelect = /\bSELECT\b/i.test(code);
        return hasSelect ? lang : null;
    }

    return lang;
}

const enhanceCourseCodeBlocks = () => {
    const copyIconMarkup = window.copyUtils && window.copyUtils.copyIconMarkup
        ? window.copyUtils.copyIconMarkup
        : "";
    document.querySelectorAll(".c-content-render pre").forEach((preEl) => {
        // ── wrap ──────────────────────────────────────────────────────────
        let wrap = preEl.parentElement;
        if (!wrap || !wrap.classList.contains("llm-code-block-wrap")) {
            wrap = document.createElement("div");
            wrap.className = "llm-code-block-wrap";
            preEl.parentNode.insertBefore(wrap, preEl);
            wrap.appendChild(preEl);
        }

        const codeEl = preEl.querySelector("code");

        if (copyIconMarkup && !wrap.querySelector(".llm-copy-code")) {
            const copyBtn = document.createElement("button");
            copyBtn.type = "button";
            copyBtn.className = "llm-copy-btn llm-copy-code";
            copyBtn.setAttribute("aria-label", "Copy code");
            copyBtn.setAttribute("title", "Copy code");
            copyBtn.setAttribute("data-copy-default", "Copy code");
            copyBtn.setAttribute("data-copy-copied", "Copied");
            copyBtn.setAttribute("data-copy-failed", "Copy failed");
            copyBtn.innerHTML = copyIconMarkup;
            copyBtn.style.position = "absolute";
            copyBtn.style.top = "0.75rem";
            copyBtn.style.right = "0.75rem";
            copyBtn.style.zIndex = "5";
            copyBtn._copyTarget = codeEl || preEl;
            wrap.appendChild(copyBtn);
        }
        // ── run button (only for Python / JS / C++) ───────────────────────
        const lang = detectRunLanguage(codeEl);
        if (lang && !wrap.querySelector(".code-run-btn")) {

            // ── "Edit" hint (shown on hover) ──────────────────────────────
            const editHint = document.createElement("span");
            editHint.className = "code-edit-hint";
            editHint.textContent = "✎";
            wrap.appendChild(editHint);

            // ── Editable textarea ─────────────────────────────────────────
            const editableCodeEl = codeEl || preEl;

            editableCodeEl.setAttribute("contenteditable", "true");
            editableCodeEl.setAttribute("spellcheck", "false");
            editableCodeEl.setAttribute("aria-label", `Editable ${LANG_LABELS[lang]} code`);

            preEl.style.cursor = "text";

            const placeCaretAtEnd = (el) => {
                const range = document.createRange();
                const selection = window.getSelection();
                range.selectNodeContents(el);
                range.collapse(false);
                selection.removeAllRanges();
                selection.addRange(range);
            };

            const enterEditMode = () => {
                wrap.classList.add("is-editing");
                editableCodeEl.focus();
            };

            preEl.addEventListener("click", () => {
                enterEditMode();
            });

            editableCodeEl.addEventListener("focus", () => {
                wrap.classList.add("is-editing");
            });

            editableCodeEl.addEventListener("keydown", (e) => {
                // Tab key → 4 spaces
                if (e.key === "Tab") {
                    e.preventDefault();
                    document.execCommand("insertText", false, "    ");
                }
            });

            document.addEventListener("click", (e) => {
                if (wrap.contains(e.target)) return;

                if (wrap.classList.contains("is-editing")) {
                    wrap.classList.remove("is-editing");

                    // Re-highlight when the user leaves the block.
                    // This keeps colors after editing.
                    if (window.hljs && codeEl) {
                        codeEl.removeAttribute("data-highlighted");
                        window.hljs.highlightElement(codeEl);
                    }
                }
            });

            // ── Run button ────────────────────────────────────────────────
            const runBtn = document.createElement("button");
            runBtn.type = "button";
            runBtn.className = "code-run-btn";
            runBtn.setAttribute("aria-label", `Run ${LANG_LABELS[lang]}`);
            runBtn.setAttribute("title",      `Run ${LANG_LABELS[lang]}`);
            runBtn.innerHTML = `
                <span class="code-run-btn__icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none">
                        <path d="M8 5.5v13l10-6.5-10-6.5Z" fill="currentColor"></path>
                    </svg>
                </span>
                <span class="code-run-btn__label">Run</span>`;
            wrap.appendChild(runBtn);

            // ── Output panel ──────────────────────────────────────────────
            const outputPanel = document.createElement("div");
            outputPanel.className = "code-output-panel";
            outputPanel.setAttribute("aria-live", "polite");
            outputPanel.hidden = true;
            outputPanel.innerHTML = `
                <div class="code-output-panel__header">
                    <span class="code-output-panel__title">Output</span>
                    <button type="button" class="code-output-panel__close" aria-label="Close output">✕</button>
                </div>
                <pre class="code-output-panel__body"></pre>`;
            wrap.appendChild(outputPanel);

            const outputBody = outputPanel.querySelector(".code-output-panel__body");
            const closeBtn   = outputPanel.querySelector(".code-output-panel__close");
            closeBtn.addEventListener("click", () => { outputPanel.hidden = true; });

            runBtn.addEventListener("click", async () => {
                // Use textarea value if editing, else original highlighted code
                wrap.classList.add("is-editing");

                const code = editableCodeEl.textContent.trim();
                if (!code) return;

                runBtn.disabled = true;
                runBtn.querySelector(".code-run-btn__label").textContent = "Running…";
                outputPanel.hidden = false;
                outputPanel.classList.remove("code-output-panel--error");
                outputBody.textContent = "⏳ Executing…";

                try {
                    const res = await fetch("/api/execute-code/", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": getCookie("csrftoken"),
                        },
                        credentials: "same-origin",
                        body: JSON.stringify({ code, language: lang }),
                    });

                    const data = await res.json();

                    if (data.error) {
                        outputPanel.classList.add("code-output-panel--error");
                        outputBody.textContent = `❌ Error: ${data.error}`;
                    } else {
                        const stdout   = data.stdout   || "";
                        const stderr   = data.stderr   || "";
                        const exitCode = data.exit_code ?? 0;

                        if (!stdout && !stderr) {
                            outputBody.textContent = exitCode === 0
                                ? "✅ Ran successfully (no output)"
                                : `⚠️ Exited with code ${exitCode}`;
                        } else {
                            outputPanel.classList.toggle("code-output-panel--error", exitCode !== 0);
                            outputBody.textContent = stdout
                                + (stderr ? `\n─── stderr ───\n${stderr}` : "");
                        }
                    }
                } catch (err) {
                    outputPanel.classList.add("code-output-panel--error");
                    outputBody.textContent = `❌ Network error: ${err.message}`;
                } finally {
                    runBtn.disabled = false;
                    runBtn.querySelector(".code-run-btn__label").textContent = "Run";
                }
            });
        }
        // ── syntax highlight ──────────────────────────────────────────────
        if (window.hljs) {
            if (codeEl) window.hljs.highlightElement(codeEl);
            else        window.hljs.highlightElement(preEl);
        }
    });

};

trackVisibleText(false);
trackAllVideos(false);
if (window.PdfViewer) {
    window.PdfViewer.initAll({
        postProgress: postContentProgress,
        onProgressPayload: applyProgressPayload,
        urlState: true,
    });
}

// Render KaTeX formulas in the course reader blocks
const initCourseMath = () => {
    if (typeof renderMathInElement !== "function") return;
    
    const contentContainers = document.querySelectorAll(".c-content-render");
    contentContainers.forEach((container) => {
        renderMathInElement(container, {
            delimiters: [
                { left: "$$", right: "$$", display: true },
                { left: "$", right: "$", display: false },
                { left: "\\(", right: "\\)", display: false },
                { left: "\\[", right: "\\]", display: true },
            ],
            throwOnError: false,
        });
    });
};

if (document.body && typeof MutationObserver === "function") {
    const bodyClassObserver = new MutationObserver((mutations) => {
        const changed = mutations.some((m) => m.attributeName === "class");
        if (changed && window.PdfViewer) schedulePdfLayoutRefresh();
    });
    bodyClassObserver.observe(document.body, { attributes: true, attributeFilter: ["class"] });
}

window.requestAnimationFrame(() => {
    applySearchTarget();
    enhanceCourseCodeBlocks();
    initCourseMath();
});