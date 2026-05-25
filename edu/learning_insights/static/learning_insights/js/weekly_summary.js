(function () {
    var readJsonScript = window.LICharts && window.LICharts.readJsonScript;
    if (typeof readJsonScript !== 'function') {
        console.warn('weekly_summary.js: li-charts.js must be loaded first.');
        return;
    }

    var CHART_COLORS = {
        study:  { bar: 'rgba(255,209,102,0.75)', border: 'rgba(255,209,102,1)' },
        site:   { border: 'rgba(42,157,102,1)',  fill: 'rgba(42,157,102,0.15)' },
        tick:   '#d7dbe7',
        grid:   'rgba(255,255,255,0.06)',
        donut:  ['rgba(255,209,102,0.85)', 'rgba(42,157,102,0.75)',
                 'rgba(138,164,255,0.75)', 'rgba(255,158,197,0.75)', 'rgba(255,123,123,0.7)'],
        border: 'rgba(0,0,0,0.15)',
    };

    // ── Daily activity (mixed bar + line) ─────────────────────────
    var dailyData   = readJsonScript('li-weekly-daily-chart-data', null);
    var dailyCanvas = document.getElementById('weekly-activity-chart');
    if (dailyData && dailyCanvas) {
        new Chart(dailyCanvas, {
            type: 'bar',
            data: {
                labels: dailyData.labels || [],
                datasets: [
                    {
                        type: 'bar',
                        label: 'Course study minutes',
                        data: dailyData.study_minutes || [],
                        backgroundColor: CHART_COLORS.study.bar,
                        borderColor: CHART_COLORS.study.border,
                        borderWidth: 1,
                        borderRadius: 8,
                    },
                    {
                        type: 'line',
                        label: 'Site active minutes',
                        data: dailyData.site_minutes || [],
                        borderColor: CHART_COLORS.site.border,
                        backgroundColor: CHART_COLORS.site.fill,
                        fill: false,
                        tension: 0.35,
                        pointRadius: 3,
                        pointHoverRadius: 4,
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
    var courseData   = readJsonScript('li-weekly-course-chart-data', null);
    var courseCanvas = document.getElementById('weekly-course-chart');
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
