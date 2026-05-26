(function () {
    var input = document.getElementById('code');
    if (!input) return;
    input.addEventListener('input', function (e) {
        var value = e.target.value.replace(/[^0-9]/g, '');
        if (value.length > 6) value = value.slice(0, 6);
        e.target.value = value;
    });
})();
