/* PDF viewer module (PDF.js) */
(function () {
    "use strict";

    const instances = new Map();
    const DEFAULT_OPTIONS = {
        maxDpr: 2,
        urlState: true,
        postProgress: null,
        onProgressPayload: null,
    };
    const WORKER_SRC = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function debounce(fn, delay) {
        let timer = null;
        return function (...args) {
            if (timer) window.clearTimeout(timer);
            timer = window.setTimeout(() => {
                timer = null;
                fn.apply(this, args);
            }, delay);
        };
    }

    function throttle(fn, delay) {
        let last = 0;
        let trailing = null;
        return function (...args) {
            const now = Date.now();
            const remaining = delay - (now - last);
            if (remaining <= 0) {
                last = now;
                fn.apply(this, args);
                return;
            }
            if (!trailing) {
                trailing = window.setTimeout(() => {
                    trailing = null;
                    last = Date.now();
                    fn.apply(this, args);
                }, remaining);
            }
        };
    }

    function buildPagesArray(numPages, fallbackSize) {
        return Array.from({ length: numPages }, () => ({
            width: fallbackSize.width,
            height: fallbackSize.height,
        }));
    }

    class PdfViewerController {
        constructor(viewerEl, options = {}) {
            this.viewerEl = viewerEl;
            this.options = { ...DEFAULT_OPTIONS, ...options };

            this.scrollEl = viewerEl.querySelector(".js-pdf-scroll");
            this.toolbar = viewerEl.querySelector(".c-pdf-toolbar");
            this.progressEl = viewerEl.querySelector(".js-pdf-progress");
            this.progressLabelEl = viewerEl.querySelector(".js-pdf-progress-label");
            this.currentEl = viewerEl.querySelector(".js-pdf-current");
            this.totalEl = viewerEl.querySelector(".js-pdf-total");
            this.pageInputEl = viewerEl.querySelector(".js-pdf-page-input");
            this.pageTotalEl = viewerEl.querySelector(".js-pdf-page-total");
            this.prevBtn = viewerEl.querySelector(".js-pdf-prev");
            this.nextBtn = viewerEl.querySelector(".js-pdf-next");
            this.zoomInBtn = viewerEl.querySelector(".js-pdf-zoom-in");
            this.zoomOutBtn = viewerEl.querySelector(".js-pdf-zoom-out");
            this.zoomSelectEl = viewerEl.querySelector(".js-pdf-zoom-select");
            this.searchInputEl = viewerEl.querySelector(".js-pdf-search-input");
            this.searchPrevBtn = viewerEl.querySelector(".js-pdf-search-prev");
            this.searchNextBtn = viewerEl.querySelector(".js-pdf-search-next");
            this.searchCountEl = viewerEl.querySelector(".js-pdf-search-count");
            this.searchToggleBtn = viewerEl.querySelector(".js-pdf-search-toggle");
            this.searchCloseBtn = viewerEl.querySelector(".js-pdf-search-close");
            this.searchHighlightToggle = viewerEl.querySelector(".js-pdf-search-toggle-highlight");
            this.searchCaseToggle = viewerEl.querySelector(".js-pdf-search-toggle-case");
            this.searchWholeToggle = viewerEl.querySelector(".js-pdf-search-toggle-whole");
            this.outlineToggleBtn = viewerEl.querySelector(".js-pdf-outline-toggle");
            this.outlineCloseBtn = viewerEl.querySelector(".js-pdf-outline-close");
            this.outlinePanelEl = viewerEl.querySelector(".js-pdf-outline-panel");
            this.outlineStatusEl = viewerEl.querySelector(".js-pdf-outline-status");
            this.outlineEmptyEl = viewerEl.querySelector(".js-pdf-outline-empty");
            this.outlineListEl = viewerEl.querySelector(".js-pdf-outline-list");
            this.brightnessInput = viewerEl.querySelector(".js-pdf-brightness");
            this.brightnessLabel = viewerEl.querySelector(".js-pdf-brightness-label");

            this.sourceUrl = viewerEl.dataset.pdfUrl || "";
            this.contentId = viewerEl.dataset.contentId || "";
            this.progressUrl = viewerEl.dataset.progressUrl || "";
            this.searchUrl = viewerEl.dataset.searchUrl || "";
            this.pageTextUrl = viewerEl.dataset.pageTextUrl || "";
            this.startPage = Math.max(1, Number(viewerEl.dataset.startPage || 1) || 1);
            this.startOffset = Number(viewerEl.dataset.startOffset || 0) || 0;
            this.startDocY = Number(viewerEl.dataset.startDocY || 0) || 0;
            this.startZoom = Number(viewerEl.dataset.startZoom || 0) || 0;
            this.maxPageSeen = Math.max(1, Number(viewerEl.dataset.maxPageSeen || this.startPage) || this.startPage);
            this.urlStateEnabled = viewerEl.dataset.urlState !== "false";

            this.pdfjsLib = window.pdfjsLib || null;
            this.doc = null;
            this.loadingTask = null;
            this.pagesLayer = null;
            this.basePageSizes = [];
            this.pageSizes = [];
            this.pageOffsets = [];
            this.renderQueue = [];
            this.renderRunning = false;
            this.renderGeneration = 0;
            this.renderedPages = new Set();
            this.pageCache = new Map();
            this.textContentCache = new Map();
            this.annotationCache = new Map();
            this.outlineLoaded = false;
            this.outlineLoading = false;
            this.outlineOpen = false;
            this.outlineItems = [];
            this.outlineDestinationCache = new Map();
            this.searchMatches = [];
            this.activeMatchIndex = -1;
            this.searchMode = false;
            this.destroyed = false;
            this.initialLayoutRefreshId = null;
            this.scrollHandler = null;
            this.resizeObserver = null;
            this.bodyObserver = null;
            this.lastSentAt = Date.now();

            this.store = {
                doc: { numPages: 0 },
                view: { scale: 1, zoomMode: "fit-width", viewportW: 0, viewportH: 0, scrollTop: 0 },
                nav: { currentPage: this.startPage },
                progress: { percent: 0 },
            };
        }

        init() {
            if (!this.sourceUrl || !this.scrollEl || !this.pdfjsLib) return this;
            if (this.pdfjsLib.GlobalWorkerOptions && !this.pdfjsLib.GlobalWorkerOptions.workerSrc) {
                this.pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_SRC;
            }

            this._initToolbar();
            this._initOutlinePanel();
            this._initThemeObserver();
            this._initBrightness();
            this._initScroll();
            void this._loadDocument();
            return this;
        }

        async _loadDocument() {
            this._setTotalText("…");
            try {
                this.loadingTask = this.pdfjsLib.getDocument(this.sourceUrl);
                this.doc = await this.loadingTask.promise;
            } catch (error) {
                this._setTotalText("error");
                return;
            }
            if (!this.doc) return;

            const numPages = this.doc.numPages || 1;
            const firstPage = await this.doc.getPage(1);
            const baseViewport = firstPage.getViewport({ scale: 1 });

            this.basePageSizes = buildPagesArray(numPages, {
                width: baseViewport.width,
                height: baseViewport.height,
            });
            this.pageSizes = this.basePageSizes.map((size) => ({ ...size }));
            this._recomputeOffsets();
            this.store.doc = { numPages };

            this._buildPagesLayer();
            this._applyInitialScale(baseViewport);
            this._restoreInitialPosition();
            this._scheduleRenderForViewport();
            this._setTotalText(numPages);
            this._scheduleInitialLayoutRefresh();
        }

        _scheduleInitialLayoutRefresh() {
            if (this.initialLayoutRefreshId !== null) return;
            this.initialLayoutRefreshId = window.setTimeout(() => {
                this.initialLayoutRefreshId = null;
                if (this.destroyed) return;
                this.refreshLayout();
            }, 120);
        }

        _buildPagesLayer() {
            this.scrollEl.innerHTML = "";
            this.pagesLayer = document.createElement("div");
            this.pagesLayer.className = "c-pdf-pages";
            this.pagesLayer.style.position = "relative";
            this.pagesLayer.style.width = "100%";
            this.pagesLayer.style.height = `${this._docHeight()}px`;
            this.scrollEl.appendChild(this.pagesLayer);
        }

        _docHeight() {
            if (!this.pageSizes.length) return 1;
            return this.pageSizes.reduce((total, size) => total + (size.height || 0) + 12, -12);
        }

        _recomputeOffsets() {
            this.pageOffsets = [];
            let top = 0;
            this.pageSizes.forEach((size, index) => {
                this.pageOffsets[index] = top;
                top += (size.height || 0) + 12;
            });
        }

        _setTotalText(value) {
            if (this.totalEl) this.totalEl.textContent = String(value);
            if (this.pageTotalEl) this.pageTotalEl.textContent = `/ ${value}`;
        }

        _applyInitialScale(baseViewport) {
            const scale = this.startZoom > 0 ? this.startZoom : this._fitWidthScale(baseViewport);
            const mode = this.startZoom > 0 ? "custom" : "fit-width";
            this._setScale(scale, mode);
        }

        _fitWidthScale(baseViewport) {
            const width = Math.max(1, this.scrollEl.clientWidth || baseViewport.width);
            return width / Math.max(1, baseViewport.width);
        }

        _fitPageScale(baseViewport) {
            const width = Math.max(1, this.scrollEl.clientWidth || baseViewport.width);
            const height = Math.max(1, this.scrollEl.clientHeight || baseViewport.height);
            return Math.min(width / Math.max(1, baseViewport.width), height / Math.max(1, baseViewport.height));
        }

        _setScale(scale, zoomMode) {
            const nextScale = clamp(Number(scale) || 1, 0.3, 4);
            this.store.view = {
                ...this.store.view,
                scale: nextScale,
                zoomMode,
                viewportW: this.scrollEl.clientWidth || 0,
                viewportH: this.scrollEl.clientHeight || 0,
            };
            this._syncZoomSelect(nextScale, zoomMode);
            this._relayoutForScale();
        }

        _syncZoomSelect(scale, zoomMode) {
            if (!this.zoomSelectEl) return;
            const percent = Math.round(scale * 100);
            if (zoomMode === "fit-width") {
                this.zoomSelectEl.value = "auto";
                return;
            }
            if (zoomMode === "fit-page") {
                this.zoomSelectEl.value = "fit-page";
                return;
            }
            if (zoomMode === "custom" && percent === 100) {
                this.zoomSelectEl.value = "actual";
                return;
            }
            const option = Array.from(this.zoomSelectEl.options).find((item) => item.value === (percent / 100).toString());
            if (option) this.zoomSelectEl.value = option.value;
        }

        _relayoutForScale() {
            if (!this.doc) return;
            const scale = this.store.view.scale;
            const anchor = this._captureScrollAnchor();
            const sourceSizes = this.basePageSizes.length ? this.basePageSizes : this.pageSizes;
            this.renderGeneration += 1;
            this.pageSizes = sourceSizes.map((size) => ({
                width: (size.width || 0) * scale,
                height: (size.height || 0) * scale,
            }));
            this._recomputeOffsets();
            if (this.pagesLayer) {
                this.pagesLayer.querySelectorAll(".c-pdf-page.is-rendered").forEach((node) => {
                    node.classList.remove("is-rendered");
                });
                this.pagesLayer.style.height = `${this._docHeight()}px`;
            }
            this._updateVisiblePagePositions();
            this.renderedPages.clear();
            this._restoreScrollAnchor(anchor);
            this._scheduleRenderForViewport();
        }

        _captureScrollAnchor() {
            if (!this.pageOffsets.length) {
                return { pageNumber: this._currentPage(), pageOffsetRatio: 0 };
            }

            const viewportH = this.scrollEl.clientHeight || 1;
            const scrollTop = this.scrollEl.scrollTop || 0;
            const anchorDocY = scrollTop + viewportH * 0.35;
            let pageIndex = 0;

            for (let i = 0; i < this.pageOffsets.length; i += 1) {
                const pageTop = this.pageOffsets[i];
                const pageHeight = this.pageSizes[i]?.height || 0;
                if (anchorDocY >= pageTop && anchorDocY <= pageTop + pageHeight) {
                    pageIndex = i;
                    break;
                }
                if (pageTop <= anchorDocY) pageIndex = i;
            }

            const pageTop = this.pageOffsets[pageIndex] || 0;
            const pageHeight = this.pageSizes[pageIndex]?.height || 1;
            return {
                pageNumber: pageIndex + 1,
                pageOffsetRatio: clamp((anchorDocY - pageTop) / Math.max(1, pageHeight), 0, 1),
            };
        }

        _restoreScrollAnchor(anchor) {
            if (!anchor || !this.pageOffsets.length) return;

            const pageIndex = clamp((Number(anchor.pageNumber) || 1) - 1, 0, Math.max(0, this.pageOffsets.length - 1));
            const pageTop = this.pageOffsets[pageIndex] || 0;
            const pageHeight = this.pageSizes[pageIndex]?.height || 1;
            const viewportH = this.scrollEl.clientHeight || 1;
            const totalHeight = this._docHeight();
            const target = pageTop + pageHeight * clamp(Number(anchor.pageOffsetRatio) || 0, 0, 1);

            this.scrollEl.scrollTop = clamp(target - viewportH * 0.35, 0, totalHeight);
            this._updateNavigationFromScroll();
        }

        _restoreInitialPosition() {
            const totalHeight = this._docHeight();
            const viewportH = this.scrollEl.clientHeight || 1;
            if (this.startDocY > 0) {
                this.scrollEl.scrollTop = clamp(this.startDocY * totalHeight - viewportH * 0.35, 0, totalHeight);
            } else if (this.startPage > 1 || this.startOffset > 0) {
                const pageIndex = clamp(this.startPage - 1, 0, Math.max(0, this.pageOffsets.length - 1));
                const pageTop = this.pageOffsets[pageIndex] || 0;
                const pageHeight = this.pageSizes[pageIndex]?.height || 1;
                const target = pageTop + pageHeight * clamp(this.startOffset, 0, 1);
                this.scrollEl.scrollTop = clamp(target - viewportH * 0.35, 0, totalHeight);
            }
            this._updateNavigationFromScroll();
        }

        _initScroll() {
            this.scrollHandler = throttle(() => {
                this._updateNavigationFromScroll();
                this._scheduleRenderForViewport();
                this._updateProgress(false);
                this._updateUrlState();
            }, 60);
            this.scrollEl.addEventListener("scroll", this.scrollHandler, { passive: true });

            this.resizeObserver = new ResizeObserver(
                debounce(() => {
                    const zoomMode = this.store.view.zoomMode;
                    if (zoomMode === "fit-width" || zoomMode === "fit-page") {
                        void this._setFitMode(zoomMode);
                    } else {
                        this._relayoutForScale();
                    }
                }, 120)
            );
            this.resizeObserver.observe(this.scrollEl);
        }

        _initThemeObserver() {
            if (!document.body || typeof MutationObserver !== "function") return;
            this.bodyObserver = new MutationObserver(() => this._syncThemeWithBody());
            this.bodyObserver.observe(document.body, { attributes: true, attributeFilter: ["class"] });
            this._syncThemeWithBody();
        }

        _syncThemeWithBody() {
            const isDark = document.body && document.body.classList.contains("theme-dark");
            this.viewerEl.classList.toggle("pdf-theme-dark", Boolean(isDark));
        }

        _initBrightness() {
            if (!this.brightnessInput) return;
            const apply = () => {
                const value = Number(this.brightnessInput.value || 1);
                const forceLight = value <= 0;
                const applied = forceLight ? 1 : value;
                this.viewerEl.classList.toggle("pdf-force-light", forceLight);
                this.viewerEl.style.setProperty("--pdf-brightness", String(applied));
                if (this.brightnessLabel) this.brightnessLabel.textContent = `${Math.round(value * 100)}%`;
            };
            this.brightnessInput.addEventListener("input", apply);
            apply();
        }

        _initToolbar() {
            if (this.searchToggleBtn) this.searchToggleBtn.addEventListener("click", () => this._setSearchMode(true));
            if (this.searchCloseBtn) this.searchCloseBtn.addEventListener("click", () => this._setSearchMode(false));
            if (this.prevBtn) this.prevBtn.addEventListener("click", () => this._jumpToPage(this._currentPage() - 1));
            if (this.nextBtn) this.nextBtn.addEventListener("click", () => this._jumpToPage(this._currentPage() + 1));
            if (this.pageInputEl) {
                this.pageInputEl.addEventListener("change", () => this._jumpToPage(Number(this.pageInputEl.value || 1)));
            }
            if (this.zoomInBtn) this.zoomInBtn.addEventListener("click", () => this._adjustZoom(0.1));
            if (this.zoomOutBtn) this.zoomOutBtn.addEventListener("click", () => this._adjustZoom(-0.1));
            if (this.zoomSelectEl) {
                this.zoomSelectEl.addEventListener("change", () => {
                    const value = this.zoomSelectEl.value;
                    if (value === "auto") return this._setFitMode("fit-width");
                    if (value === "fit-page") return this._setFitMode("fit-page");
                    if (value === "actual") return this._setScale(1, "custom");
                    const parsed = Number(value);
                    if (Number.isFinite(parsed) && parsed > 0) this._setScale(parsed, "custom");
                });
            }
            if (this.searchInputEl) {
                const runSearch = debounce(() => this._search(this.searchInputEl.value || ""), 220);
                this.searchInputEl.addEventListener("input", runSearch);
                this.searchInputEl.addEventListener("keydown", (event) => {
                    if (event.key === "Enter") {
                        event.preventDefault();
                        this._search(this.searchInputEl.value || "");
                    }
                    if (event.key === "Escape") {
                        event.preventDefault();
                        this._setSearchMode(false);
                    }
                });
                this.searchInputEl.addEventListener("focus", () => this._setSearchMode(true));
            }
            if (this.searchPrevBtn) this.searchPrevBtn.addEventListener("click", () => this._stepMatch(-1));
            if (this.searchNextBtn) this.searchNextBtn.addEventListener("click", () => this._stepMatch(1));
            if (this.searchHighlightToggle) {
                this.searchHighlightToggle.addEventListener("click", () => {
                    const next = this.searchHighlightToggle.getAttribute("aria-pressed") !== "true";
                    this.searchHighlightToggle.setAttribute("aria-pressed", String(next));
                });
            }
            if (this.searchCaseToggle) {
                this.searchCaseToggle.addEventListener("click", () => {
                    const next = this.searchCaseToggle.getAttribute("aria-pressed") !== "true";
                    this.searchCaseToggle.setAttribute("aria-pressed", String(next));
                });
            }
            if (this.searchWholeToggle) {
                this.searchWholeToggle.addEventListener("click", () => {
                    const next = this.searchWholeToggle.getAttribute("aria-pressed") !== "true";
                    this.searchWholeToggle.setAttribute("aria-pressed", String(next));
                });
            }
        }

        _initOutlinePanel() {
            if (this.outlineToggleBtn) {
                this.outlineToggleBtn.addEventListener("click", () => {
                    const next = !this.outlineOpen;
                    this._setOutlineOpen(next);
                    if (next) void this._loadOutline();
                });
            }
            if (this.outlineCloseBtn) {
                this.outlineCloseBtn.addEventListener("click", (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    this._setOutlineOpen(false);
                });
            }
            this._setOutlineOpen(false);
        }

        _setOutlineOpen(open) {
            this.outlineOpen = Boolean(open);
            if (this.outlinePanelEl) this.outlinePanelEl.hidden = !this.outlineOpen;
            if (this.outlineToggleBtn) this.outlineToggleBtn.setAttribute("aria-expanded", String(this.outlineOpen));
            this.viewerEl.classList.toggle("has-outline-open", this.outlineOpen);
        }

        async _loadOutline() {
            if (this.outlineLoaded || this.outlineLoading || !this.doc) return;
            this.outlineLoading = true;
            this._renderOutlinePlaceholder("Loading outline…");
            try {
                const outline = await this.doc.getOutline();
                this.outlineItems = Array.isArray(outline) ? outline : [];
            } catch (error) {
                this.outlineItems = [];
            } finally {
                this.outlineLoaded = true;
                this.outlineLoading = false;
                this._renderOutline();
            }
        }

        _renderOutlinePlaceholder(message) {
            if (!this.outlineEmptyEl) return;
            this.outlineEmptyEl.hidden = false;
            this.outlineEmptyEl.textContent = message;
            if (this.outlineListEl) this.outlineListEl.innerHTML = "";
            if (this.outlineStatusEl) this.outlineStatusEl.hidden = true;
        }

        _renderOutline() {
            if (!this.outlineEmptyEl || !this.outlineListEl) return;
            this.outlineListEl.innerHTML = "";
            if (!this.outlineItems.length) {
                this._renderOutlinePlaceholder("No document outline is available for this PDF.");
                return;
            }
            this.outlineEmptyEl.hidden = true;
            const fragment = document.createDocumentFragment();
            this.outlineItems.forEach((item) => {
                const node = this._createOutlineNode(item, 0);
                if (node) fragment.appendChild(node);
            });
            this.outlineListEl.appendChild(fragment);
        }

        _createOutlineNode(item, depth) {
            if (!item || !item.title) return null;
            const li = document.createElement("li");
            li.className = "c-pdf-outline__item";

            const control = item.url || item.unsafeUrl ? document.createElement("a") : document.createElement("button");
            control.className = "c-pdf-outline__link";
            control.textContent = item.title;
            control.title = item.title;
            control.style.paddingLeft = `${0.8 + depth * 0.6}rem`;

            if (control.tagName === "A") {
                control.href = item.unsafeUrl || item.url;
                control.target = item.newWindow ? "_blank" : "_self";
                if (control.target === "_blank") control.rel = "noopener noreferrer";
            } else {
                control.type = "button";
                control.addEventListener("click", () => void this._navigateToDestination(item.dest));
            }

            li.appendChild(control);
            if (Array.isArray(item.items) && item.items.length) {
                const childList = document.createElement("ul");
                childList.className = "c-pdf-outline__children";
                item.items.forEach((child) => {
                    const childNode = this._createOutlineNode(child, depth + 1);
                    if (childNode) childList.appendChild(childNode);
                });
                li.appendChild(childList);
            }
            return li;
        }

        async _navigateToDestination(dest) {
            if (!this.doc || !dest) return;
            let resolved = dest;
            try {
                if (typeof dest === "string") {
                    resolved = await this.doc.getDestination(dest);
                }
            } catch (error) {
                return;
            }
            if (!Array.isArray(resolved) || !resolved.length) return;

            let pageIndex = null;
            const pageRef = resolved[0];
            try {
                if (typeof pageRef === "number") {
                    pageIndex = Math.max(0, pageRef - 1);
                } else if (pageRef) {
                    if (this.outlineDestinationCache.has(pageRef)) {
                        pageIndex = this.outlineDestinationCache.get(pageRef);
                    } else {
                        pageIndex = await this.doc.getPageIndex(pageRef);
                        this.outlineDestinationCache.set(pageRef, pageIndex);
                    }
                }
            } catch (error) {
                pageIndex = null;
            }
            if (pageIndex === null || pageIndex < 0) return;
            this._jumpToPage(pageIndex + 1);
        }

        _createPageNode(pageNumber) {
            const pageIndex = pageNumber - 1;
            const size = this.pageSizes[pageIndex] || { width: 0, height: 0 };
            const top = this.pageOffsets[pageIndex] || 0;
            const node = document.createElement("div");
            node.className = "c-pdf-page js-pdf-page";
            node.dataset.pageNumber = String(pageNumber);
            node.style.position = "absolute";
            node.style.left = "0";
            node.style.top = `${top}px`;
            node.style.width = "100%";
            node.style.height = `${size.height}px`;

            const canvas = document.createElement("canvas");
            canvas.className = "c-pdf-page__canvas js-pdf-canvas";
            canvas.setAttribute("aria-label", `PDF page ${pageNumber}`);
            node.appendChild(canvas);

            const textLayer = document.createElement("div");
            textLayer.className = "c-pdf-page__text-layer js-pdf-text-layer";
            node.appendChild(textLayer);

            const highlightLayer = document.createElement("div");
            highlightLayer.className = "c-pdf-page__highlights js-pdf-highlights";
            node.appendChild(highlightLayer);

            const annotationLayer = document.createElement("div");
            annotationLayer.className = "c-pdf-page__annotations js-pdf-annotations";
            node.appendChild(annotationLayer);

            return node;
        }

        _visiblePageRange() {
            if (!this.pageOffsets.length) return { start: 1, end: 1 };
            const scrollTop = this.scrollEl.scrollTop || 0;
            const viewportH = this.scrollEl.clientHeight || 1;
            const startY = Math.max(0, scrollTop - viewportH * 0.5);
            const endY = scrollTop + viewportH * 1.5;

            const findIndex = (y) => {
                let index = 0;
                for (let i = 0; i < this.pageOffsets.length; i += 1) {
                    const pageTop = this.pageOffsets[i];
                    const pageHeight = this.pageSizes[i]?.height || 0;
                    if (y >= pageTop && y <= pageTop + pageHeight) return i;
                    if (pageTop <= y) index = i;
                }
                return index;
            };

            return {
                start: clamp(findIndex(startY), 0, this.pageOffsets.length - 1) + 1,
                end: clamp(findIndex(endY), 0, this.pageOffsets.length - 1) + 1,
            };
        }

        _ensureRenderedWindow() {
            const { start, end } = this._visiblePageRange();
            const windowStart = Math.max(0, start - 1 - 2);
            const windowEnd = Math.min(this.pageSizes.length - 1, end - 1 + 2);
            const keep = new Set();

            for (let index = windowStart; index <= windowEnd; index += 1) {
                const pageNumber = index + 1;
                keep.add(pageNumber);
                let node = this.pagesLayer.querySelector(`[data-page-number="${pageNumber}"]`);
                if (!node) {
                    node = this._createPageNode(pageNumber);
                    this.pagesLayer.appendChild(node);
                } else {
                    node.style.top = `${this.pageOffsets[index] || 0}px`;
                    node.style.height = `${this.pageSizes[index]?.height || 0}px`;
                }
                this._queueRender(pageNumber, pageNumber >= start && pageNumber <= end ? 2 : 1);
            }

            Array.from(this.pagesLayer.querySelectorAll(".js-pdf-page")).forEach((node) => {
                const pageNumber = Number(node.dataset.pageNumber || 0);
                if (!keep.has(pageNumber)) {
                    this.renderedPages.delete(pageNumber);
                    node.remove();
                }
            });
        }

        _queueRender(pageNumber, priority) {
            if (this.renderedPages.has(pageNumber)) return;
            if (this.renderQueue.some((item) => item.pageNumber === pageNumber)) return;
            this.renderQueue.push({ pageNumber, priority });
            this.renderQueue.sort((a, b) => b.priority - a.priority);
            void this._runRenderQueue();
        }

        async _runRenderQueue() {
            if (this.renderRunning) return;
            this.renderRunning = true;
            const generation = ++this.renderGeneration;
            while (this.renderQueue.length) {
                if (generation !== this.renderGeneration) break;
                const item = this.renderQueue.shift();
                if (!item) continue;
                try {
                    await this._renderPage(item.pageNumber, generation);
                } catch (error) {
                    // ignore render failures
                }
            }
            this.renderRunning = false;
            if (this.renderQueue.length) {
                void this._runRenderQueue();
            }
        }

        async _renderPage(pageNumber, generation) {
            if (!this.doc || !this.pagesLayer) return;
            const node = this.pagesLayer.querySelector(`[data-page-number="${pageNumber}"]`);
            if (!node) return;

            const page = await this._getPage(pageNumber);
            if (!page) return;
            const scale = this.store.view.scale;
            const baseViewport = page.getViewport({ scale: 1 });
            const viewport = page.getViewport({ scale });
            const dpr = clamp(window.devicePixelRatio || 1, 1, this.options.maxDpr);

            const canvas = node.querySelector(".js-pdf-canvas");
            const textLayer = node.querySelector(".js-pdf-text-layer");
            const annotationLayer = node.querySelector(".js-pdf-annotations");
            const highlightLayer = node.querySelector(".js-pdf-highlights");
            if (!canvas || !textLayer || !annotationLayer) return;

            canvas.width = Math.floor(viewport.width * dpr);
            canvas.height = Math.floor(viewport.height * dpr);
            canvas.style.width = `${Math.floor(viewport.width)}px`;
            canvas.style.height = `${Math.floor(viewport.height)}px`;
            canvas.style.pointerEvents = "none";

            const context = canvas.getContext("2d");
            if (!context) return;
            context.setTransform(dpr, 0, 0, dpr, 0, 0);

            await page.render({ canvasContext: context, viewport }).promise;
            if (generation !== this.renderGeneration) return;

            node.style.height = `${Math.floor(viewport.height)}px`;
            textLayer.style.width = `${Math.floor(viewport.width)}px`;
            textLayer.style.height = `${Math.floor(viewport.height)}px`;
            annotationLayer.style.width = `${Math.floor(viewport.width)}px`;
            annotationLayer.style.height = `${Math.floor(viewport.height)}px`;
            if (highlightLayer) {
                highlightLayer.style.width = `${Math.floor(viewport.width)}px`;
                highlightLayer.style.height = `${Math.floor(viewport.height)}px`;
            }

            this.pageSizes[pageNumber - 1] = { width: baseViewport.width * scale, height: baseViewport.height * scale };
            this._recomputeOffsets();
            this.pagesLayer.style.height = `${this._docHeight()}px`;
            this._updateVisiblePagePositions();
            if (!node.isConnected) return;
            this.renderedPages.add(pageNumber);
            this._renderTextLayer(page, viewport, textLayer);
            this._renderAnnotations(page, viewport, annotationLayer);
            this._applySearchHighlightsToPage(pageNumber);
            node.classList.add("is-rendered");
            this._updateProgress(false);
        }

        _getPage(pageNumber) {
            if (!this.doc) return Promise.resolve(null);
            if (!this.pageCache.has(pageNumber)) {
                this.pageCache.set(
                    pageNumber,
                    this.doc.getPage(pageNumber).catch((error) => {
                        this.pageCache.delete(pageNumber);
                        throw error;
                    })
                );
            }
            return this.pageCache.get(pageNumber);
        }

        _updateVisiblePagePositions() {
            if (!this.pagesLayer) return;
            Array.from(this.pagesLayer.querySelectorAll(".js-pdf-page")).forEach((node) => {
                const pageNumber = Number(node.dataset.pageNumber || 0);
                const index = pageNumber - 1;
                node.style.top = `${this.pageOffsets[index] || 0}px`;
                node.style.height = `${this.pageSizes[index]?.height || 0}px`;
            });
        }

        async _renderTextLayer(page, viewport, textLayerEl) {
            if (!textLayerEl) return;
            textLayerEl.textContent = "";
            let textContent = this.textContentCache.get(page.pageNumber);
            if (!textContent) {
                textContent = await page.getTextContent();
                this.textContentCache.set(page.pageNumber, textContent);
            }

            if (typeof this.pdfjsLib.TextLayer === "function") {
                try {
                    const textLayer = new this.pdfjsLib.TextLayer({
                        textContentSource: textContent,
                        container: textLayerEl,
                        viewport,
                    });
                    const maybePromise = textLayer.render();
                    if (maybePromise && typeof maybePromise.then === "function") await maybePromise;
                    return;
                } catch (error) {
                    // fallback below
                }
            }

            if (typeof this.pdfjsLib.renderTextLayer === "function") {
                try {
                    const task = this.pdfjsLib.renderTextLayer({
                        container: textLayerEl,
                        viewport,
                        enhanceTextSelection: true,
                        textContent,
                        textContentSource: textContent,
                    });
                    if (task && task.promise) await task.promise;
                    else if (task && typeof task.then === "function") await task;
                    return;
                } catch (error) {
                    // fallback below
                }
            }

            this._renderTextLayerFallback(textLayerEl, textContent, viewport);
        }

        _renderTextLayerFallback(textLayerEl, textContent, viewport) {
            const util = this.pdfjsLib && this.pdfjsLib.Util;
            if (!util || !textLayerEl || !textContent || !Array.isArray(textContent.items)) return;
            const styles = textContent.styles || {};
            const fragment = document.createDocumentFragment();

            textContent.items.forEach((item) => {
                if (!item || typeof item.str !== "string" || !item.str.length) return;
                const style = styles[item.fontName] || {};
                const tx = util.transform(util.transform(viewport.transform, item.transform), [1, 0, 0, -1, 0, 0]);
                const fontHeight = Math.hypot(tx[2], tx[3]);
                if (!Number.isFinite(fontHeight) || fontHeight <= 0) return;

                const span = document.createElement("span");
                span.textContent = item.str;
                span.dir = item.dir || "ltr";
                span.style.position = "absolute";
                span.style.whiteSpace = "pre";
                span.style.transformOrigin = "0 0";
                span.style.color = "rgba(0, 0, 0, 0.01)";
                span.style.webkitTextFillColor = "rgba(0, 0, 0, 0.01)";
                span.style.cursor = "text";
                span.style.webkitUserSelect = "text";
                span.style.userSelect = "text";
                span.style.left = `${tx[4]}px`;
                span.style.top = `${tx[5] - fontHeight}px`;
                span.style.fontSize = `${fontHeight}px`;
                span.style.fontFamily = style.fontFamily || "sans-serif";
                fragment.appendChild(span);
            });

            textLayerEl.appendChild(fragment);
        }

        async _renderAnnotations(page, viewport, annotationLayerEl) {
            if (!annotationLayerEl) return;
            annotationLayerEl.textContent = "";
            let annotations = this.annotationCache.get(page.pageNumber);
            if (!annotations) {
                try {
                    annotations = await page.getAnnotations({ intent: "display" });
                    this.annotationCache.set(page.pageNumber, annotations);
                } catch (error) {
                    return;
                }
            }
            if (!Array.isArray(annotations) || !annotations.length) return;

            const fragment = document.createDocumentFragment();
            annotations.forEach((annotation) => {
                if (!annotation || annotation.subtype !== "Link" || !Array.isArray(annotation.rect)) return;
                const rect = viewport.convertToViewportRectangle(annotation.rect);
                const left = Math.min(rect[0], rect[2]);
                const top = Math.min(rect[1], rect[3]);
                const width = Math.abs(rect[2] - rect[0]);
                const height = Math.abs(rect[3] - rect[1]);
                if (width <= 0 || height <= 0) return;

                const element = document.createElement(annotation.url || annotation.unsafeUrl ? "a" : "button");
                element.className = "c-pdf-link";
                element.style.left = `${left}px`;
                element.style.top = `${top}px`;
                element.style.width = `${width}px`;
                element.style.height = `${height}px`;
                element.title = annotation.contents || annotation.url || annotation.unsafeUrl || "Link";

                if (element.tagName === "A") {
                    element.href = annotation.unsafeUrl || annotation.url;
                    element.target = annotation.newWindow ? "_blank" : "_self";
                    if (element.target === "_blank") element.rel = "noopener noreferrer";
                    element.setAttribute("aria-label", element.title);
                } else {
                    element.type = "button";
                    element.setAttribute("aria-label", element.title);
                    element.addEventListener("click", () => {
                        if (annotation.dest) void this._navigateToDestination(annotation.dest);
                    });
                }
                fragment.appendChild(element);
            });
            annotationLayerEl.appendChild(fragment);
        }

        _setSearchMode(enabled) {
            this.searchMode = Boolean(enabled);
            if (this.toolbar) {
                this.toolbar.classList.toggle("is-search-active", this.searchMode);
                this.toolbar.dataset.toolbarState = this.searchMode ? "search" : "default";
            }
            if (this.searchMode && this.searchInputEl) {
                this.searchInputEl.focus({ preventScroll: true });
                this.searchInputEl.select();
            }
        }

        _adjustZoom(delta) {
            this._setScale(this.store.view.scale + delta, "custom");
        }

        async _setFitMode(mode) {
            if (!this.doc) return;
            const firstPage = await this.doc.getPage(1);
            const baseViewport = firstPage.getViewport({ scale: 1 });
            const scale = mode === "fit-page" ? this._fitPageScale(baseViewport) : this._fitWidthScale(baseViewport);
            this._setScale(scale, mode);
        }

        _currentPage() {
            return this.store.nav.currentPage || 1;
        }

        _jumpToPage(page) {
            const total = this.pageSizes.length || 1;
            const target = clamp(Number(page) || 1, 1, total);
            const index = target - 1;
            const top = this.pageOffsets[index] || 0;
            this.scrollEl.scrollTo({ top: clamp(top, 0, this._docHeight()), behavior: "auto" });
            this._updateNavigationFromScroll();
            this._scheduleRenderForViewport();
        }

        _updateNavigationFromScroll() {
            const viewportH = this.scrollEl.clientHeight || 1;
            const scrollTop = this.scrollEl.scrollTop || 0;
            const anchorY = scrollTop + viewportH * 0.35;
            let currentPage = 1;

            for (let i = 0; i < this.pageOffsets.length; i += 1) {
                const pageTop = this.pageOffsets[i];
                const pageHeight = this.pageSizes[i]?.height || 0;
                if (anchorY >= pageTop && anchorY <= pageTop + pageHeight) {
                    currentPage = i + 1;
                    break;
                }
                if (pageTop <= anchorY) currentPage = i + 1;
            }

            if (this.currentEl) this.currentEl.textContent = String(currentPage);
            if (this.pageInputEl) this.pageInputEl.value = String(currentPage);
            this.store.nav = { currentPage };
            this.store.view = {
                ...this.store.view,
                scrollTop,
                viewportW: this.scrollEl.clientWidth || 0,
                viewportH,
            };
        }

        _scheduleRenderForViewport() {
            if (!this.doc || !this.pagesLayer) return;
            this._ensureRenderedWindow();
        }

        _search(query) {
            const normalized = String(query || "").trim();
            if (!normalized) {
                this.searchMatches = [];
                this.activeMatchIndex = -1;
                this._updateSearchUI();
                this._clearSearchHighlights();
                return;
            }
            if (!this.searchUrl) return;

            const url = new URL(this.searchUrl, window.location.origin);
            url.searchParams.set("q", normalized);
            fetch(url.toString(), { credentials: "same-origin" })
                .then((response) => (response.ok ? response.json() : null))
                .then((data) => {
                    this.searchMatches = Array.isArray(data && data.matches) ? data.matches : [];
                    this.activeMatchIndex = this.searchMatches.length ? 0 : -1;
                    this._updateSearchUI();
                    if (this.searchMatches.length) this._jumpToMatch(this.activeMatchIndex);
                })
                .catch(() => {
                    // ignore
                });
        }

        _updateSearchUI() {
            if (!this.searchCountEl) return;
            this.searchCountEl.textContent = this.searchMatches.length ? `${this.activeMatchIndex + 1} / ${this.searchMatches.length}` : "";
        }

        _stepMatch(direction) {
            if (!this.searchMatches.length) return;
            const total = this.searchMatches.length;
            let next = this.activeMatchIndex + direction;
            if (next < 0) next = total - 1;
            if (next >= total) next = 0;
            this.activeMatchIndex = next;
            this._updateSearchUI();
            this._jumpToMatch(next);
        }

        _jumpToMatch(index) {
            const match = this.searchMatches[index];
            if (!match) return;
            this._jumpToPage(Number(match.page || 1));
            window.setTimeout(() => this._applySearchHighlightsToPage(Number(match.page || 1)), 250);
        }

        _clearSearchHighlights() {
            if (!this.pagesLayer) return;
            this.pagesLayer.querySelectorAll(".c-pdf-highlight").forEach((item) => item.remove());
        }

        _applySearchHighlightsToPage(pageNumber) {
            if (!this.searchInputEl || !this.searchInputEl.value || !this.pagesLayer) return;
            const query = this.searchInputEl.value.trim().toLowerCase();
            if (!query) return;
            const pageNode = this.pagesLayer.querySelector(`[data-page-number="${pageNumber}"]`);
            if (!pageNode) return;
            const highlightLayer = pageNode.querySelector(".js-pdf-highlights");
            if (!highlightLayer) return;
            highlightLayer.textContent = "";

            Array.from(pageNode.querySelectorAll(".js-pdf-text-layer span")).forEach((span) => {
                const text = (span.textContent || "").toLowerCase();
                if (!text.includes(query)) return;
                const rect = span.getBoundingClientRect();
                const parentRect = pageNode.getBoundingClientRect();
                const highlight = document.createElement("div");
                highlight.className = "c-pdf-highlight";
                highlight.style.left = `${rect.left - parentRect.left}px`;
                highlight.style.top = `${rect.top - parentRect.top}px`;
                highlight.style.width = `${rect.width}px`;
                highlight.style.height = `${rect.height}px`;
                highlightLayer.appendChild(highlight);
            });
        }

        _updateProgress(force) {
            const currentPage = this.store.nav.currentPage || 1;
            this.maxPageSeen = Math.max(this.maxPageSeen, currentPage);
            const totalPages = this.pageSizes.length || 1;
            const percent = clamp((this.maxPageSeen / totalPages) * 100, 0, 100);

            if (this.progressEl) {
                this.progressEl.style.setProperty("--pdf-progress", `${Math.round(percent)}%`);
                this.progressEl.setAttribute("aria-valuenow", String(Math.round(percent)));
                this.progressEl.classList.toggle("is-complete", percent >= 100);
            }
            if (this.progressLabelEl) {
                this.progressLabelEl.textContent = percent >= 100 ? "\u2714" : `${Math.round(percent)}%`;
            }

            this.store.progress = { percent };
            this._sendProgress(force);
        }

        _sendProgress(force) {
            if (!this.progressUrl) return;
            const now = Date.now();
            const secondsDelta = Math.max(0, Math.floor((now - this.lastSentAt) / 1000));
            if (!force && secondsDelta < 5) return;
            this.lastSentAt = now;

            const viewportH = this.scrollEl.clientHeight || 1;
            const scrollTop = this.scrollEl.scrollTop || 0;
            const anchorDocY = scrollTop + viewportH * 0.35;
            let pageIndex = 0;
            for (let i = 0; i < this.pageOffsets.length; i += 1) {
                const pageTop = this.pageOffsets[i];
                const pageHeight = this.pageSizes[i]?.height || 0;
                if (anchorDocY >= pageTop && anchorDocY <= pageTop + pageHeight) {
                    pageIndex = i;
                    break;
                }
                if (pageTop <= anchorDocY) pageIndex = i;
            }

            const payload = {
                kind: "pdf",
                current_page: pageIndex + 1,
                total_pages: this.pageSizes.length,
                max_page_seen: Math.max(this.maxPageSeen, pageIndex + 1),
                doc_progress: this.store.progress.percent,
                doc_y_ratio: clamp(anchorDocY / Math.max(1, this._docHeight()), 0, 1),
                page_offset_ratio: clamp(
                    (anchorDocY - (this.pageOffsets[pageIndex] || 0)) /
                        Math.max(1, this.pageSizes[pageIndex]?.height || 1),
                    0,
                    1
                ),
                zoom: this.store.view.scale,
                viewport_w: this.store.view.viewportW,
                viewport_h: this.store.view.viewportH,
                seconds_delta: secondsDelta,
            };

            const send = this.options.postProgress
                ? this.options.postProgress(this.progressUrl, payload, { keepalive: force })
                : fetch(this.progressUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": this._getCookie("csrftoken"),
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    credentials: "same-origin",
                    keepalive: Boolean(force),
                    body: JSON.stringify(payload),
                }).then((response) => (response.ok ? response.json().catch(() => null) : null));

            Promise.resolve(send).then((data) => {
                if (data && typeof this.options.onProgressPayload === "function") {
                    this.options.onProgressPayload(data);
                }
            });
        }

        _getCookie(name) {
            const cookies = document.cookie ? document.cookie.split("; ") : [];
            for (const cookie of cookies) {
                const [key, ...rest] = cookie.split("=");
                if (key === name) return decodeURIComponent(rest.join("="));
            }
            return "";
        }

        _updateUrlState() {
            if (!this.options.urlState || !this.urlStateEnabled) return;
            const params = new URLSearchParams(window.location.search);
            params.set("content_id", String(this.contentId || ""));
            params.set("page", String(this.store.nav.currentPage || 1));
            params.set("zoom", String(this.store.view.scale.toFixed(2)));
            const nextUrl = `${window.location.pathname}?${params.toString()}`;
            this._replaceState(nextUrl);
        }

        _replaceState(url) {
            if (!this._replaceStateThrottled) {
                this._replaceStateThrottled = throttle((nextUrl) => {
                    window.history.replaceState({}, "", nextUrl);
                }, 180);
            }
            this._replaceStateThrottled(url);
        }

        refreshLayout() {
            if (this.initialLayoutRefreshId !== null) {
                window.clearTimeout(this.initialLayoutRefreshId);
                this.initialLayoutRefreshId = null;
            }
            const zoomMode = this.store.view.zoomMode;
            if (zoomMode === "fit-width" || zoomMode === "fit-page") {
                void this._setFitMode(zoomMode);
            } else {
                this._relayoutForScale();
            }
        }

        setAutoZoom() {
            void this._setFitMode("fit-width");
        }

        flushProgress(force) {
            this._updateProgress(Boolean(force));
        }

        destroy() {
            this.destroyed = true;
            if (this.initialLayoutRefreshId !== null) {
                window.clearTimeout(this.initialLayoutRefreshId);
                this.initialLayoutRefreshId = null;
            }
            if (this.scrollHandler) this.scrollEl.removeEventListener("scroll", this.scrollHandler);
            if (this.resizeObserver) this.resizeObserver.disconnect();
            if (this.bodyObserver) this.bodyObserver.disconnect();
            this.renderQueue = [];
            this.renderedPages.clear();
            this.pageCache.clear();
            this.textContentCache.clear();
            this.annotationCache.clear();
            if (this.loadingTask && typeof this.loadingTask.destroy === "function") {
                this.loadingTask.destroy().catch(() => {});
            }
        }
    }

    function initAll(options = {}) {
        const viewerEls = Array.from(document.querySelectorAll(".js-pdf-viewer"));
        viewerEls.forEach((el) => {
            if (instances.has(el)) return;
            const controller = new PdfViewerController(el, options);
            instances.set(el, controller);
            controller.init();
        });
        return instances;
    }

    function refreshAll() {
        instances.forEach((controller) => controller.refreshLayout());
    }

    function setAutoZoomAll() {
        instances.forEach((controller) => controller.setAutoZoom());
    }

    function flushAll() {
        instances.forEach((controller) => controller.flushProgress(true));
    }

    function destroyAll() {
        instances.forEach((controller) => controller.destroy());
        instances.clear();
    }

    window.PdfViewer = { initAll, refreshAll, setAutoZoomAll, flushAll, destroyAll };
})();
