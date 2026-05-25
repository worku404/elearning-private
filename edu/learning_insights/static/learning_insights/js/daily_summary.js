(function () {
    var readJsonScript = window.LICharts && window.LICharts.readJsonScript;
    if (typeof readJsonScript !== 'function') {
        console.warn('daily_summary.js: li-charts.js must be loaded first.');
        return;
    }

    var courseData = readJsonScript('li-daily-course-chart-data', null);
    var canvas     = document.getElementById('daily-course-chart');
    if (!courseData || !canvas) return;

    var labels  = courseData.labels  || [];
    var minutes = courseData.minutes || [];
    if (!labels.length || !minutes.length) return;

    new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: minutes,
                backgroundColor: ['#ffd54f', '#ff9ec5', '#2ecc71', '#3498db', '#9b59b6'],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 10 },
                },
            },
        },
    });
})();
