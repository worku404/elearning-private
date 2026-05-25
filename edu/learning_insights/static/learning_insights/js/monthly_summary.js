(function () {
    var readJsonScript = window.LICharts && window.LICharts.readJsonScript;
    if (typeof readJsonScript !== 'function') {
        console.warn('monthly_summary.js: li-charts.js must be loaded first.');
        return;
    }

    var CHART_COLORS = {
        study:   { border: 'rgba(255, 209, 102, 1)', fill: 'rgba(255, 209, 102, 0.12)' },
        site:    { border: 'rgba(42, 157, 102, 1)',  fill: 'rgba(42, 157, 102, 0.12)' },
        tick:    '#d7dbe7',
        grid:    'rgba(255,255,255,0.06)',
        donut:   ['rgba(255,209,102,0.85)', 'rgba(42,157,102,0.75)',
                  'rgba(138,164,255,0.75)', 'rgba(255,158,197,0.75)', 'rgba(255,123,123,0.7)'],
        border:  'rgba(0,0,0,0.15)',
    };

    // ── Daily trend (line chart) ──────────────────────────────────
    var dailyData  = readJsonScript('li-monthly-daily-chart-data', null);
    var dailyCanvas = document.getElementById('monthly-trend-chart');
    if (dailyData && dailyCanvas) {
        new Chart(dailyCanvas, {
            type: 'line',
            data: {
                labels: dailyData.labels || [],
                datasets: [
                    {
                        label: 'Course study minutes',
                        data: dailyData.study_minutes || [],
                        borderColor: CHART_COLORS.study.border,
                        backgroundColor: CHART_COLORS.study.fill,
                        tension: 0.35, pointRadius: 2, pointHoverRadius: 3,
                    },
                    {
                        label: 'Site active minutes',
                        data: dailyData.site_minutes || [],
                        borderColor: CHART_COLORS.site.border,
                        backgroundColor: CHART_COLORS.site.fill,
                        tension: 0.35, pointRadius: 2, pointHoverRadius: 3,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: CHART_COLORS.tick }, grid: { color: CHART_COLORS.grid } },
                    y: { ticks: { color: CHART_COLORS.tick }, grid: { color: CHART_COLORS.grid } },
                },
                plugins: { legend: { labels: { color: CHART_COLORS.tick } } },
            },
        });
    }

    // ── Top courses (doughnut) ────────────────────────────────────
    var courseData  = readJsonScript('li-monthly-course-chart-data', null);
    var courseCanvas = document.getElementById('monthly-course-chart');
    if (courseData && courseCanvas) {
        new Chart(courseCanvas, {
            type: 'doughnut',
            data: {
                labels: courseData.labels || [],
                datasets: [{
                    label: 'Minutes',
                    data: courseData.minutes || [],
                    backgroundColor: CHART_COLORS.donut,
                    borderColor: CHART_COLORS.border,
                    borderWidth: 1,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: CHART_COLORS.tick } } },
            },
        });
    }
})();
