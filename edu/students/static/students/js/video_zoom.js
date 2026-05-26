(function () {
    const zoomClass = "is-zoom-fill";
    const containers = Array.from(document.querySelectorAll(".c-video"));
    let activeContainer = null;

    function isEditableTarget(target) {
        if (!target) return false;
        const tag = target.tagName ? target.tagName.toLowerCase() : "";
        if (tag === "input" || tag === "textarea" || tag === "select") return true;
        return Boolean(target.isContentEditable);
    }

    function setActive(container) {
        if (!container) return;
        activeContainer = container;
    }

    function getFirstVideoContainer() {
        return containers.find((container) => container.querySelector("video")) || null;
    }

    containers.forEach((container) => {
        const video = container.querySelector("video");
        if (!video) return;
        container.classList.add("js-video-zoomable");
        video.addEventListener("play", () => setActive(container));
        video.addEventListener("click", () => setActive(container));
        container.addEventListener("click", () => setActive(container));
    });

    window.addEventListener("keydown", (event) => {
        if (!event.ctrlKey || !event.shiftKey || event.code !== "KeyZ") return;
        if (isEditableTarget(event.target)) return;

        const container = activeContainer || getFirstVideoContainer();
        if (!container) return;

        event.preventDefault();
        container.classList.toggle(zoomClass);
    });
})();
