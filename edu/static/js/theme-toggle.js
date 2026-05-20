(function () {
    const themeStorageKey = "theme_preference";
    const defaultMode = "dark";
    const body = document.body;
    const html = document.documentElement;
    const toggleLink = document.getElementById("theme-toggle-link");

    if (!body || !toggleLink) return;

    const applyTheme = function (mode) {
        const darkModeEnabled = mode === "dark";
        body.classList.toggle("theme-dark", darkModeEnabled);
        html.classList.toggle("theme-dark", darkModeEnabled);
        html.style.colorScheme = darkModeEnabled ? "dark" : "light";
        const icon = toggleLink.querySelector(".theme-icon");

        if (icon) {
            icon.innerHTML = darkModeEnabled
                ? '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><circle cx="12" cy="12" r="5"/><g stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="6.34" y2="6.34"/><line x1="17.66" y1="17.66" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="6.34" y2="17.66"/><line x1="17.66" y1="6.34" x2="19.78" y2="4.22"/></g></svg>'
                : '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M21 12.79A9 9 0 0 1 11.21 3 7 7 0 1 0 21 12.79z"/></svg>';
        }

        toggleLink.setAttribute("aria-pressed", String(darkModeEnabled));
    };

    let preferredMode = defaultMode;
    try {
        const storedMode = localStorage.getItem(themeStorageKey);
        if (storedMode === "dark" || storedMode === "light") {
            preferredMode = storedMode;
        } else {
            localStorage.setItem(themeStorageKey, defaultMode);
        }
    } catch (error) {
        preferredMode = defaultMode;
    }

    applyTheme(preferredMode);

    toggleLink.addEventListener("click", function (event) {
        event.preventDefault();
        const nextMode = body.classList.contains("theme-dark") ? "light" : "dark";
        applyTheme(nextMode);
        try {
            localStorage.setItem(themeStorageKey, nextMode);
        } catch (error) {
            // Ignore storage failures.
        }
    });
})();
