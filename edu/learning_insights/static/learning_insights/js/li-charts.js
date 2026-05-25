/**
 * Shared Learning Insights chart utilities.
 * Must be loaded before any individual chart-init scripts.
 */
window.LICharts = window.LICharts || {};

/**
 * Read and parse JSON that Django's json_script filter embedded in the page.
 * @param {string} id       – the element id given to json_script
 * @param {*}      fallback – value returned when the element is absent or unparseable
 */
window.LICharts.readJsonScript = function (id, fallback) {
    var node = document.getElementById(id);
    if (!node) return fallback;
    try {
        return JSON.parse(node.textContent);
    } catch (e) {
        return fallback;
    }
};
