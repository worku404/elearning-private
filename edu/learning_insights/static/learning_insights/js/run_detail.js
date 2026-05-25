(function () {
    var container  = document.getElementById('li-plan-items');
    var addBtn     = document.getElementById('li-plan-add');
    var template   = document.getElementById('li-plan-empty-form');
    var totalInput = document.getElementById('id_items-TOTAL_FORMS');
    if (!container || !addBtn || !template || !totalInput) return;

    addBtn.addEventListener('click', function () {
        var total   = parseInt(totalInput.value || '0', 10);
        var html    = template.innerHTML.replaceAll('__prefix__', String(total));
        var wrapper = document.createElement('div');
        wrapper.innerHTML = html.trim();
        var node = wrapper.firstElementChild;
        if (!node) return;
        container.appendChild(node);
        totalInput.value = String(total + 1);
        var dayInput = node.querySelector("input[type='date']");
        if (dayInput) dayInput.focus();
    });
})();
