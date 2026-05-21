(function () {
    const items = Array.from(document.querySelectorAll("[data-notification]"));
    if (!items.length) return;

    const AUTO_HIDE_MS = 4500;

    items.forEach((item) => {
        const closeBtn = item.querySelector("[data-notification-close]");
        let timer = null;

        function remove() {
            item.style.transition = "opacity 180ms ease, transform 180ms ease";
            item.style.opacity = "0";
            item.style.transform = "translateY(-6px)";
            window.setTimeout(() => {
                item.remove();
            }, 200);
        }

        function startTimer() {
            if (timer) return;
            timer = window.setTimeout(remove, AUTO_HIDE_MS);
        }

        function stopTimer() {
            if (!timer) return;
            window.clearTimeout(timer);
            timer = null;
        }

        if (closeBtn) {
            closeBtn.addEventListener("click", remove);
        }

        item.addEventListener("mouseenter", stopTimer);
        item.addEventListener("mouseleave", startTimer);
        item.addEventListener("focusin", stopTimer);
        item.addEventListener("focusout", startTimer);

        startTimer();
    });
})();

