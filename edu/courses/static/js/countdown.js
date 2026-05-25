(function () {
    var countdownEl = document.getElementById('exam-countdown');
    if (!countdownEl) return;

    var daysEl    = document.getElementById('countdown-days');
    var hoursEl   = document.getElementById('countdown-hours');
    var minutesEl = document.getElementById('countdown-minutes');
    var secondsEl = document.getElementById('countdown-seconds');

    // Date is supplied via data-exam-date on the element — falls back to the
    // original hardcoded value so existing markup without the attribute is safe.
    var examDateStr = countdownEl.getAttribute('data-exam-date') || '2026-06-04T00:00:00';
    var examDate    = new Date(examDateStr).getTime();

    function pad(n) { return String(n).padStart(2, '0'); }

    function updateCountdown() {
        var now           = Date.now();
        var timeRemaining = examDate - now;

        if (timeRemaining <= 0) {
            if (daysEl)    daysEl.textContent    = '00';
            if (hoursEl)   hoursEl.textContent   = '00';
            if (minutesEl) minutesEl.textContent = '00';
            if (secondsEl) secondsEl.textContent = '00';
            countdownEl.classList.remove('countdown--caution', 'countdown--warning');
            countdownEl.classList.add('countdown--critical');
            return;
        }

        var days    = Math.floor(timeRemaining / (1000 * 60 * 60 * 24));
        var hours   = Math.floor((timeRemaining % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        var minutes = Math.floor((timeRemaining % (1000 * 60 * 60)) / (1000 * 60));
        var seconds = Math.floor((timeRemaining % (1000 * 60)) / 1000);

        if (daysEl)    daysEl.textContent    = pad(days);
        if (hoursEl)   hoursEl.textContent   = pad(hours);
        if (minutesEl) minutesEl.textContent = pad(minutes);
        if (secondsEl) secondsEl.textContent = pad(seconds);

        countdownEl.classList.remove('countdown--caution', 'countdown--warning', 'countdown--critical');
        if (days <= 10 && hours < 24) {
            countdownEl.classList.add('countdown--critical');
        } else if (days <= 15) {
            countdownEl.classList.add('countdown--warning');
        }
    }

    updateCountdown();
    setInterval(updateCountdown, 1000);
})();
