// Extracted from courses/base.html — Block 4 IIFEs
// URLs supplied via data-* attributes on #js-app-config (rendered by Django)
(function () {
    "use strict";
    var cfg = document.getElementById("js-app-config");
    if (!cfg) return;

    var pingUrl       = cfg.dataset.presenceUrl             || "";
    var chatBootstrap = cfg.dataset.chatBootstrapUrl        || "";
    var liBootstrap   = cfg.dataset.liBootstrapUrl          || "";
    var liNotifCenter = cfg.dataset.liNotificationCenterUrl || "";

    document.addEventListener("DOMContentLoaded", () => {
            const focusRoot = document.querySelector("[data-focus-modules]");
            if (!focusRoot) return;

            const toggleBtn = focusRoot.querySelector("[data-focus-toggle]");
            const listEl = focusRoot.querySelector("[data-focus-list]");
            if (!toggleBtn || !listEl) return;

            toggleBtn.addEventListener("click", () => {
                const nextOpen = toggleBtn.getAttribute("aria-expanded") !== "true";
                toggleBtn.setAttribute("aria-expanded", String(nextOpen));
                toggleBtn.textContent = nextOpen ? "Hide" : "More";
                listEl.hidden = !nextOpen;
            });
        });

    (function () {
        const badgeEls = Array.from(document.querySelectorAll("[data-presence-badge]"));
        const countEls = Array.from(document.querySelectorAll("[data-presence-count]"));
        const dotEls = badgeEls
            .map((badgeEl) => badgeEl.querySelector(".c-presence__dot"))
            .filter(Boolean);

        if (!badgeEls.length || !countEls.length) return;

        const HEARTBEAT_MS = 30000;
        let timerId = null;

        function getCookie(name) {
            const cookie = document.cookie
                .split("; ")
                .find((row) => row.startsWith(name + "="));
            return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
        }

        function setLiveState(isLive) {
            dotEls.forEach((dotEl) => {
                dotEl.style.background = isLive ? "#2ecc71" : "#7f8c8d";
            });
            badgeEls.forEach((badgeEl) => {
                badgeEl.style.opacity = isLive ? "1" : "0.75";
            });
        }

        async function pingPresence() {
            try {
                const response = await fetch(pingUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });

                if (!response.ok) {
                    setLiveState(false);
                    return;
                }

                const data = await response.json();
                const onlineCount = Number.parseInt(data.online_count, 10);
                const value = Number.isFinite(onlineCount) ? String(onlineCount) : "0";
                countEls.forEach((countEl) => {
                    countEl.textContent = value;
                });
                setLiveState(true);
            } catch (error) {
                setLiveState(false);
            }
        }

        function startHeartbeat() {
            if (timerId !== null) return;
            timerId = window.setInterval(pingPresence, HEARTBEAT_MS);
        }

        function stopHeartbeat() {
            if (timerId === null) return;
            window.clearInterval(timerId);
            timerId = null;
        }

        // First load
        pingPresence();
        startHeartbeat();

        // Re-ping when tab becomes active
        document.addEventListener("visibilitychange", function () {
            if (document.hidden) {
                stopHeartbeat();
            } else {
                pingPresence();
                startHeartbeat();
            }
        });

        window.addEventListener("beforeunload", stopHeartbeat);
    })();
    (function () {
        const stack = document.getElementById("chat-notification-stack");
        if (!stack) return;

        const shownMessageIds = new Set();
        let socket = null;
        let reconnectDelay = 1000;

        function escapeHtml(value) {
            return String(value)
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
        }

        function isInsideSameChatRoom(courseId) {
            const path = window.location.pathname || "";
            return path === `/chat/room/${courseId}/`;
        }

        function createToast(item) {
            if (!item || !item.message_id) return null;
            if (shownMessageIds.has(item.message_id)) return null;
            if (isInsideSameChatRoom(item.course_id)) return null;

            shownMessageIds.add(item.message_id);

            const toast = document.createElement("article");
            toast.className = "c-toast";
            toast.innerHTML = `
                <div class="c-toast__head">
                    <strong class="c-toast__title">${escapeHtml(item.course_title || "Course chat")}</strong>
                    <button type="button" class="c-toast__close" aria-label="Dismiss notification">&times;</button>
                </div>
                <p class="c-toast__meta">
                    ${escapeHtml(item.from_user || "User")} sent a message
                </p>
                <p class="c-toast__body">${escapeHtml(item.message_preview || "")}</p>
                <a class="c-toast__link" href="/chat/room/${item.course_id}/">Open chat</a>
            `;

            const closeBtn = toast.querySelector(".c-toast__close");
            if (closeBtn) {
                closeBtn.addEventListener("click", () => {
                    toast.remove();
                });
            }

            setTimeout(() => {
                toast.remove();
            }, 20000);

            return toast;
        }

        function showToast(item) {
            const toast = createToast(item);
            if (!toast) return;
            stack.prepend(toast);
        }

        function connectNotificationSocket() {
            const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
            socket = new WebSocket(`${wsScheme}://${window.location.host}/ws/notify/`);

            socket.onopen = function () {
                reconnectDelay = 1000;
            };

            socket.onmessage = function (event) {
                try {
                    const payload = JSON.parse(event.data);
                    showToast(payload);
                } catch (error) {
                    // Ignore malformed payloads.
                }
            };

            socket.onclose = function () {
                setTimeout(connectNotificationSocket, reconnectDelay);
                reconnectDelay = Math.min(reconnectDelay * 2, 30000);
            };
        }

        let shouldBootstrap = true;
        try {
            const bootstrapKey = "chat_notifications_bootstrap_done";
            if (sessionStorage.getItem(bootstrapKey) === "1") {
                shouldBootstrap = false;
            } else {
                sessionStorage.setItem(bootstrapKey, "1");
            }
        } catch (error) {
            shouldBootstrap = true;
        }

        if (shouldBootstrap) {
            fetch(chatBootstrap, {
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            })
                .then((response) => response.ok ? response.json() : { items: [] })
                .then((data) => {
                    (data.items || []).forEach((item) => {
                        showToast(item);
                    });
                })
                .catch(() => {
                    // Silent failure.
                });
        }

        connectNotificationSocket();
    })();

    (function () {
        const stack = document.getElementById("chat-notification-stack");
        if (!stack) return;

        const shownInsightIds = new Set();

        function escapeHtml(value) {
            return String(value)
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
        }

        function isInsideInsightsNotifications() {
            const path = window.location.pathname || "";
            return path.startsWith("/insights/notifications");
        }

        function createToast(item) {
            if (!item || !item.id) return null;
            if (shownInsightIds.has(item.id)) return null;
            if (isInsideInsightsNotifications()) return null;

            shownInsightIds.add(item.id);

            const toast = document.createElement("article");
            toast.className = "c-toast";

            const title = escapeHtml(item.title || "Learning Insights");
            const body = escapeHtml(item.body || "");
            const url = item.url || liNotifCenter;

            toast.innerHTML = `
                <div class="c-toast__head">
                    <strong class="c-toast__title">${title}</strong>
                    <button type="button" class="c-toast__close" aria-label="Dismiss notification">&times;</button>
                </div>
                <p class="c-toast__meta">Learning Insights</p>
                <p class="c-toast__body">${body}</p>
                <a class="c-toast__link" href="${escapeHtml(url)}">Open</a>
            `;

            const closeBtn = toast.querySelector(".c-toast__close");
            if (closeBtn) {
                closeBtn.addEventListener("click", () => {
                    toast.remove();
                });
            }

            setTimeout(() => {
                toast.remove();
            }, 20000);

            return toast;
        }

        function showToast(item) {
            const toast = createToast(item);
            if (!toast) return;
            stack.prepend(toast);
        }

        const POLL_MS = 30000;
        let pollTimerId = null;
        let pollInFlight = false;

        function pollNotifications() {
            if (pollInFlight) return;
            if (document.hidden) return;
            if (isInsideInsightsNotifications()) return;

            pollInFlight = true;
            fetch(liBootstrap, {
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            })
                .then((response) => (response.ok ? response.json() : { items: [] }))
                .then((data) => {
                    (data.items || []).forEach((item) => {
                        showToast(item);
                    });
                })
                .catch(() => {
                    // Silent failure.
                })
                .finally(() => {
                    pollInFlight = false;
                });
        }

        function startPolling() {
            if (pollTimerId !== null) return;
            pollTimerId = window.setInterval(pollNotifications, POLL_MS);
        }

        function stopPolling() {
            if (pollTimerId === null) return;
            window.clearInterval(pollTimerId);
            pollTimerId = null;
        }

        let params = null;
        let forceBootstrap = false;
        try {
            params = new URLSearchParams(window.location.search || "");
            forceBootstrap = params.get("li_bootstrap") === "1";
        } catch (error) {
            params = null;
            forceBootstrap = false;
        }

        if (forceBootstrap) {
            try {
                sessionStorage.setItem("insights_notifications_bootstrap_done", "1");
            } catch (error) {
                // Ignore session storage errors.
            }
        }

        function clearForceParam() {
            if (!forceBootstrap || !params) return;
            params.delete("li_bootstrap");
            const queryString = params.toString();
            const nextUrl =
                window.location.pathname +
                (queryString ? "?" + queryString : "") +
                (window.location.hash || "");
            try {
                history.replaceState(null, "", nextUrl);
            } catch (error) {
                // Ignore history errors.
            }
        }

        let shouldBootstrap = forceBootstrap;
        if (!shouldBootstrap) {
            try {
                const bootstrapKey = "insights_notifications_bootstrap_done";
                if (sessionStorage.getItem(bootstrapKey) === "1") {
                    shouldBootstrap = false;
                } else {
                    sessionStorage.setItem(bootstrapKey, "1");
                    shouldBootstrap = true;
                }
            } catch (error) {
                shouldBootstrap = true;
            }
        }

        if (shouldBootstrap) {
            fetch(liBootstrap, {
                credentials: "same-origin",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            })
                .then((response) => (response.ok ? response.json() : { items: [] }))
                .then((data) => {
                    (data.items || []).forEach((item) => {
                        showToast(item);
                    });
                    clearForceParam();
                })
                .catch(() => {
                    clearForceParam();
                    // Silent failure.
                });
        } else {
            clearForceParam();
        }

        pollNotifications();
        startPolling();

        document.addEventListener("visibilitychange", function () {
            if (document.hidden) {
                stopPolling();
            } else {
                pollNotifications();
                startPolling();
            }
        });

        window.addEventListener("beforeunload", stopPolling);
    })();

    (function () {
        const refreshBtn = document.querySelector("[data-motto-refresh]");
        if (!refreshBtn) return;

        const textEl = document.querySelector("[data-motto-text]");
        const contextEl = document.querySelector("[data-motto-context]");
        const noteEl = document.querySelector("[data-motto-note]");
        const linkEl = document.querySelector("[data-motto-link]");
        const refreshUrl = refreshBtn.getAttribute("data-motto-refresh-url");
        const defaultLabel =
            refreshBtn.getAttribute("data-motto-refresh-label") || "Refresh insight";
        const defaultAriaLabel = refreshBtn.getAttribute("aria-label") || defaultLabel;
        const defaultTitle = refreshBtn.getAttribute("title") || defaultLabel;
        const defaultLinkLabel = linkEl ? (linkEl.textContent || "Link").trim() : "Link";

        function setLoading(isLoading) {
            refreshBtn.classList.toggle("is-loading", isLoading);
            refreshBtn.disabled = isLoading;
            refreshBtn.setAttribute(
                "aria-label",
                isLoading ? "Refreshing insight" : defaultAriaLabel
            );
            refreshBtn.setAttribute("title", isLoading ? "Refreshing..." : defaultTitle);
        }

        function applyMotto(motto) {
            if (!motto) return;
            if (textEl && motto.text) {
                textEl.textContent = motto.text;
            }
            if (noteEl) {
                noteEl.textContent = motto.source || "Knowledge";
            }
            if (contextEl) {
                const link = (motto.link || "").trim();
                contextEl.hidden = !link;
            }
            if (linkEl) {
                const link = (motto.link || "").trim();
                if (link) {
                    linkEl.hidden = false;
                    linkEl.href = link;
                    linkEl.textContent = defaultLinkLabel;
                    linkEl.setAttribute("title", motto.source ? `Open article on ${motto.source}` : "Open article");
                } else {
                    linkEl.hidden = true;
                    linkEl.removeAttribute("href");
                }
            }
        }

        refreshBtn.addEventListener("click", async () => {
            if (!refreshUrl) return;
            setLoading(true);
            try {
                const response = await fetch(refreshUrl, {
                    method: "GET",
                    cache: "no-store",
                    credentials: "same-origin",
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                    },
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || "Unable to refresh.");
                }
                applyMotto(data.motto);
            } catch (error) {
                refreshBtn.classList.add("is-error");
                refreshBtn.setAttribute("aria-label", "Refresh failed");
                refreshBtn.setAttribute("title", "Refresh failed");
                window.setTimeout(() => {
                    refreshBtn.classList.remove("is-error");
                    refreshBtn.setAttribute("aria-label", defaultAriaLabel);
                    refreshBtn.setAttribute("title", defaultTitle);
                }, 1400);
            } finally {
                setLoading(false);
            }
        });
    })();

})();
