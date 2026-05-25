(function () {
    const toggle = document.querySelector("[data-account-menu-toggle]");
    const menu = document.querySelector("[data-account-menu]");
    const overlay = document.querySelector("[data-account-menu-overlay]");
    if (!toggle || !menu || !overlay) return;

    function openMenu() {
        menu.hidden = false;
        overlay.hidden = false;
        menu.classList.add("is-open");
        overlay.classList.add("is-open");
        toggle.setAttribute("aria-expanded", "true");
        menu.setAttribute("aria-hidden", "false");
        overlay.setAttribute("aria-hidden", "false");
    }

    function closeMenu() {
        menu.classList.remove("is-open");
        overlay.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        menu.setAttribute("aria-hidden", "true");
        overlay.setAttribute("aria-hidden", "true");
        // Wait for transition to finish, then fully hide.
        window.setTimeout(() => {
            if (!menu.classList.contains("is-open")) {
                menu.hidden = true;
                overlay.hidden = true;
            }
        }, 250);
    }

    toggle.addEventListener("click", function (event) {
        event.preventDefault();
        if (menu.classList.contains("is-open")) {
            closeMenu();
        } else {
            openMenu();
        }
    });

    overlay.addEventListener("click", closeMenu);

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeMenu();
        }
    });
})();
