import { handleCopy } from "../utils/copy.js";

document.addEventListener("DOMContentLoaded", () => {
  const statusEl = document.getElementById("copy-token-status");
  const buttons = Array.from(document.querySelectorAll("[data-copy-text]"));
  if (!buttons.length) return;

  buttons.forEach((button) => {
    button.addEventListener("click", async () => {
      const textToCopy = button.getAttribute("data-copy-text") || "";
      if (!textToCopy) return;

      const copied = await handleCopy(button, textToCopy);
      const successMessage =
        button.getAttribute("data-copy-success") || "Copied to clipboard.";
      const failureMessage =
        button.getAttribute("data-copy-failure") || "Clipboard access failed.";

      if (statusEl) {
        statusEl.textContent = copied ? successMessage : failureMessage;
      }

      if (!copied) {
        const selectTarget = button.getAttribute("data-copy-select");
        if (!selectTarget) return;
        const field = document.querySelector(selectTarget);
        if (field && typeof field.select === "function") {
          field.select();
        }
      }
    });
  });
});
