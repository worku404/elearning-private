// Standalone Chat Window Launcher
// Opens the AI Assistant in a dedicated browser popup window.
document.addEventListener("DOMContentLoaded", () => {
    // Prevent action inside the standalone window itself
    if (document.body.classList.contains("is-standalone-window")) {
        document.body.classList.remove("assistant-hidden");
        document.body.classList.add("assistant-sidebar-open");
        const popout = document.querySelector(".assistant-new-window");
        if (popout) {
            popout.style.display = "none";
        }
        return;
    }

    const popoutButton = document.querySelector(".assistant-new-window");
    if (!popoutButton) return;

    popoutButton.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const standaloneUrl = "/assistant/llm/standalone/";
        const windowFeatures = [
            "width=480",
            "height=720",
            "menubar=no",
            "toolbar=no",
            "location=no",
            "status=no",
            "resizable=yes",
            "scrollbars=yes",
        ].join(",");

        window.open(standaloneUrl, "AssistantStandaloneChat", windowFeatures);
    });
});
