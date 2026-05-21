(function () {
    var header = document.getElementById("header");
    var toggle = document.getElementById("topbar-menu-toggle");
    var drawer = document.getElementById("topbar-drawer");
    if (!header || !toggle || !drawer) return;

    var mq = window.matchMedia("(max-width: 900px)");

    function setOpen(open) {
        header.classList.toggle("topbar--drawer-open", open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    }

    toggle.addEventListener("click", function () {
        if (!mq.matches) return;
        setOpen(!header.classList.contains("topbar--drawer-open"));
    });

    drawer.addEventListener("click", function (e) {
        if (!mq.matches) return;
        if (e.target.closest("#notes-open-btn") || e.target.closest("[data-account-menu-toggle]")) {
            setOpen(false);
            return;
        }
        if (e.target.closest('button[type="submit"]') && e.target.closest("form.topbar__search")) {
            setOpen(false);
            return;
        }
        var link = e.target.closest("a[href]");
        if (!link) return;
        var href = link.getAttribute("href") || "";
        if (href !== "#" && !href.startsWith("#")) {
            setOpen(false);
        }
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && mq.matches) {
            setOpen(false);
        }
    });

    window.addEventListener("resize", function () {
        if (!mq.matches) {
            setOpen(false);
        }
    });
})();
