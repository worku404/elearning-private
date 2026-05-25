(function () {
    var textarea = document.getElementById('ai-prompt');
    var sendBtn  = document.getElementById('ai-prompt-send');
    if (!textarea) return;

    function sync() {
        textarea.style.height = 'auto';
        var next = Math.min(120, Math.max(36, textarea.scrollHeight || 36));
        textarea.style.height = next + 'px';
        if (sendBtn) sendBtn.disabled = textarea.value.trim().length === 0;
    }

    textarea.addEventListener('input', sync);
    textarea.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            if (sendBtn && !sendBtn.disabled) {
                var form = sendBtn.closest('form');
                if (form) form.submit();
            }
        }
    });

    sync();
})();
