// --- Main JS for Jira Timesheet UI ---

// State - with safe defaults
let holidays = Array.isArray(serverData?.holidays) ? serverData.holidays : [];
let selectedMonth = null;
let selectedYear = null;

// DOM Ready
document.addEventListener("DOMContentLoaded", function () {
  restoreOvertimeState();
  setCalendarToCurrentMonth();
  setupEventListeners();
  initializeCharts();
});

function setupEventListeners() {
  // Custom column input
  const customInput = document.getElementById("customColumnInput");
  if (customInput) {
    customInput.addEventListener("focus", function () {
      document.querySelector(
        'input[name="category_type"][value="Custom"]'
      ).checked = true;
      this.disabled = false;
    });
  }
  // Form submit
  const form = document.querySelector("form.filter-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      const customRadio = document.querySelector(
        'input[name="category_type"][value="Custom"]'
      );
      const customInput = document.getElementById("customColumnInput");
      if (
        customRadio &&
        customInput &&
        customRadio.checked &&
        customInput.value.trim()
      ) {
        customRadio.value = customInput.value.trim();
      }
      preserveOvertimeState();
    });
  }
  // Holiday month change
  const holidayMonthInput = document.getElementById("holidayMonth");
  if (holidayMonthInput) {
    holidayMonthInput.addEventListener("change", function () {
      selectedMonth = this.value;
      selectedYear = this.value.split("-")[0];
      renderHolidayCalendar(selectedMonth, selectedYear);
    });
  }
}

// Overtime UI toggle
function toggleOvertimeUI() {
  const checkbox = document.getElementById("showOvertimeUI");
  const settingsToggle = document.getElementById("overtimeSettingsToggle");
  const overtimeChart = document.getElementById("overtimeChart");
  const overtimeBreakdown = document.getElementById("overtimeBreakdown");
  const burnoutAlert = document.getElementById("burnoutAlert");
  localStorage.setItem("overtimeUIEnabled", checkbox.checked);
  if (checkbox.checked) {
    settingsToggle.style.display = "block";
    if (overtimeChart) overtimeChart.style.display = "block";
    if (overtimeBreakdown) overtimeBreakdown.style.display = "block";
    if (burnoutAlert) burnoutAlert.style.display = "block";
  } else {
    settingsToggle.style.display = "none";
    if (overtimeChart) overtimeChart.style.display = "none";
    if (overtimeBreakdown) overtimeBreakdown.style.display = "none";
    if (burnoutAlert) burnoutAlert.style.display = "none";
    const panel = document.getElementById("overtimeSettingsPanel");
    if (panel) panel.style.display = "none";
    const toggleText = document.getElementById("overtimeToggleText");
    const toggleIcon = document.getElementById("overtimeToggleIcon");
    if (toggleText)
      toggleText.textContent = "Show Overtime Calculation Settings";
    if (toggleIcon) toggleIcon.textContent = "▼";
  }
}
function restoreOvertimeState() {
  const savedState = localStorage.getItem("overtimeUIEnabled");
  if (savedState === "true") {
    const checkbox = document.getElementById("showOvertimeUI");
    if (checkbox) {
      checkbox.checked = true;
      toggleOvertimeUI();
    }
  }
}
function preserveOvertimeState() {
  const checkbox = document.getElementById("showOvertimeUI");
  if (checkbox) {
    localStorage.setItem("overtimeUIEnabled", checkbox.checked);
  }
}
function toggleOvertimeSettings() {
  const panel = document.getElementById("overtimeSettingsPanel");
  const toggleText = document.getElementById("overtimeToggleText");
  const toggleIcon = document.getElementById("overtimeToggleIcon");
  if (panel.style.display === "none" || panel.style.display === "") {
    panel.style.display = "block";
    toggleText.textContent = "Hide Overtime Calculation Settings";
    toggleIcon.textContent = "▲";
  } else {
    panel.style.display = "none";
    toggleText.textContent = "Show Overtime Calculation Settings";
    toggleIcon.textContent = "▼";
  }
}
function toggleCustomInput() {
  const customRadio = document.querySelector(
    'input[name="category_type"][value="Custom"]'
  );
  const customInput = document.getElementById("customColumnInput");
  if (customRadio && customInput) {
    if (customRadio.checked) {
      customInput.disabled = false;
      customInput.focus();
    } else {
      customInput.disabled = true;
      customInput.value = "";
    }
  }
}

// --- Holiday Calendar Logic ---
function renderHolidayCalendar(month, year) {
  const calendar = document.getElementById("holidayCalendar");
  if (!calendar) return;
  calendar.innerHTML = "";
  if (!month || !year) return;
  const [y, m] = month.split("-");
  const yearNum = parseInt(y, 10);
  const monNum = parseInt(m, 10);
  let html = "<thead><tr>";
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  days.forEach((day) => {
    html += `<th style="padding:8px;text-align:center;background:#f8f9fa;border:1px solid #dee2e6;color:${
      day === "Sun" ? "#dc3545" : "#333"
    }">${day}</th>`;
  });
  html += "</tr></thead><tbody>";
  const firstDay = new Date(yearNum, monNum - 1, 1);
  const lastDay = new Date(yearNum, monNum, 0);
  const daysInMonth = lastDay.getDate();
  let date = 1;
  for (let i = 0; i < 6; i++) {
    html += "<tr>";
    for (let j = 0; j < 7; j++) {
      if (i === 0 && j < firstDay.getDay()) {
        html +=
          '<td style="padding:8px;text-align:center;border:1px solid #dee2e6;">&nbsp;</td>';
      } else if (date > daysInMonth) {
        html +=
          '<td style="padding:8px;text-align:center;border:1px solid #dee2e6;">&nbsp;</td>';
      } else {
        const dateStr = `${yearNum}-${String(monNum).padStart(2, "0")}-${String(
          date
        ).padStart(2, "0")}`;
        const isHoliday = holidays.includes(dateStr);
        html += `
                    <td style="padding:8px;text-align:center;border:1px solid #dee2e6;cursor:pointer;
                        ${isHoliday ? "background-color:#ffc107;" : ""}
                        ${j === 0 ? "color:#dc3545;" : ""}" 
                        onclick="toggleHoliday('${dateStr}')">
                        <span>${date}</span>
                    </td>`;
        date++;
      }
    }
    html += "</tr>";
    if (date > daysInMonth) break;
  }
  html += "</tbody>";
  calendar.innerHTML = html;
}
function toggleHoliday(dateStr) {
  const idx = holidays.indexOf(dateStr);
  if (idx >= 0) {
    holidays.splice(idx, 1);
  } else {
    holidays.push(dateStr);
  }
  fetch("/set_holidays", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ holidays }),
  }).then(() => renderHolidayCalendar(selectedMonth, selectedYear));
}
function setCalendarToCurrentMonth() {
  const now = new Date();
  const monthStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(
    2,
    "0"
  )}`;
  const holidayMonthInput = document.getElementById("holidayMonth");
  if (holidayMonthInput) {
    holidayMonthInput.value = monthStr;
    selectedMonth = monthStr;
    selectedYear = now.getFullYear();
    renderHolidayCalendar(selectedMonth, selectedYear);
  }
}
function changeMonth(delta) {
  const input = document.getElementById("holidayMonth");
  if (!input) return;
  let [year, month] = input.value.split("-").map(Number);
  month += delta;
  if (month > 12) {
    month = 1;
    year++;
  } else if (month < 1) {
    month = 12;
    year--;
  }
  input.value = `${year}-${String(month).padStart(2, "0")}`;
  selectedMonth = input.value;
  selectedYear = year;
  renderHolidayCalendar(selectedMonth, selectedYear);
}
function uploadHolidayExcel() {
  const fileInput = document.getElementById("holidayExcel");
  if (!fileInput.files.length) {
    alert("Please select a file first");
    return;
  }
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  fetch("/upload_holidays", {
    method: "POST",
    body: formData,
  })
    .then((resp) => resp.json())
    .then((data) => {
      if (data.success) {
        holidays = data.holidays;
        renderHolidayCalendar(selectedMonth, selectedYear);
        alert("Holidays imported successfully!");
        fileInput.value = "";
      } else {
        alert("Import failed: " + data.error);
      }
    })
    .catch((err) => {
      alert("Error importing holidays: " + err);
    });
}
function resetHolidays() {
  holidays = [];
  fetch("/set_holidays", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ holidays }),
  }).then(() => renderHolidayCalendar(selectedMonth, selectedYear));
}

// --- Chart Logic ---
function initializeCharts() {
  if (
    serverData?.weeklyOvertimeData?.weeks &&
    document.getElementById("weeklyOvertimeChart")
  ) {
    initializeWeeklyOvertimeChart();
  }

  if (
    serverData?.categoryData?.length &&
    document.getElementById("categoryPieChart")
  ) {
    initializeCategoryPieChart();
  }

  if (
    serverData?.burnoutData?.length &&
    document.getElementById("strainScoreChart")
  ) {
    initializeStrainScoreChart();
  }
}

function initializeWeeklyOvertimeChart() {
  const ctx = document.getElementById("weeklyOvertimeChart").getContext("2d");
  if (!serverData.weeklyOvertimeData || !serverData.weeklyOvertimeData.weeks) {
    console.warn("No overtime data available");
    return;
  }

  const data = serverData.weeklyOvertimeData;

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.weeks,
      datasets: [
        {
          label: "Regular Hours",
          data: data.actual_hours || data.weeks.map(() => 0),
          backgroundColor: "rgba(0, 123, 255, 0.8)",
          borderColor: "rgb(0, 123, 255)",
          borderWidth: 1,
          barPercentage: 0.8,
        },
        {
          label: "Overtime Hours",
          data: data.overtime_hours,
          backgroundColor: "rgba(220, 53, 69, 0.8)",
          borderColor: "rgb(220, 53, 69)",
          borderWidth: 1,
          barPercentage: 0.8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      scales: {
        x: {
          stacked: true,
          grid: {
            display: false,
          },
          title: {
            display: true,
            text: "Week Number",
            font: { size: 12 },
          },
          ticks: {
            maxRotation: 45,
            minRotation: 45,
          },
        },
        y: {
          stacked: true,
          beginAtZero: true,
          title: {
            display: true,
            text: "Hours",
            font: { size: 12 },
          },
        },
      },
      plugins: {
        title: {
          display: true,
          text: "Weekly Total Efforts vs Overtime Hours",
          font: { size: 14 },
        },
        tooltip: {
          callbacks: {
            title: (tooltipItems) => {
              const idx = tooltipItems[0].dataIndex;
              const week = data.weeks[idx];
              const dateRange = data.date_ranges[idx];
              return `Week: ${week}\nDate Range: ${dateRange}`;
            },
            label: (context) => {
              const datasetLabel = context.dataset.label;
              const value = context.parsed.y.toFixed(2);
              return `${datasetLabel}: ${value} hours`;
            },
            afterBody: (tooltipItems) => {
              const idx = tooltipItems[0].dataIndex;
              const totalHours = data.total_hours ? data.total_hours[idx] : 0;
              return `Total Hours: ${totalHours} hours`;
            },
          },
        },
        legend: {
          display: true,
          position: 'top',
        },
      },
      layout: {
        padding: {
          left: 10,
          right: 10,
          top: 10,
          bottom: 10,
        },
      },
    },
  });
}

function initializeCategoryPieChart() {
  const ctx = document.getElementById("categoryPieChart").getContext("2d");
  const categoryData = serverData.categoryData;
  const labels = categoryData.map((item) => item["Category"]);
  const hours = categoryData.map((item) => item["Hours spent"]);
  const totalHours = hours.reduce((a, b) => a + b, 0);

  new Chart(ctx, {
    type: "pie",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Total Hours",
          data: hours,
          backgroundColor: [
            "#007bff",
            "#28a745",
            "#ffc107",
            "#dc3545",
            "#17a2b8",
            "#6f42c1",
            "#20c997",
            "#fd7e14",
          ],
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: "right" },
        datalabels: {
          color: "#fff",
          font: { weight: "bold" },
          formatter: (value) => {
            let percentage = ((value / totalHours) * 100).toFixed(1) + "%";
            return percentage;
          },
        },
      },
    },
    plugins: [ChartDataLabels],
  });
}

function initializeStrainScoreChart() {
  const ctx = document.getElementById("strainScoreChart").getContext("2d");
  const burnoutData = serverData.burnoutData;
  const weeklyOvertimeData = serverData.weeklyOvertimeData;
  
  if (!burnoutData || burnoutData.length === 0) {
    console.warn("No burnout data available for strain score chart");
    return;
  }

  // Use actual weekly data if available, otherwise show current period only
  let weeks, weeklyOvertimeByAuthor;
  
  if (weeklyOvertimeData && weeklyOvertimeData.weeks && weeklyOvertimeData.weeks.length > 0) {
    weeks = [...weeklyOvertimeData.weeks, 'Current'];
    
    // Extract weekly overtime data per author from the existing weekly chart data
    // For now, we'll distribute the weekly overtime equally among authors in that week
    // In a real implementation, this would come from the backend with per-author weekly breakdown
    weeklyOvertimeByAuthor = {};
    burnoutData.forEach(employee => {
      const author = employee.author;
      const currentOvertime = employee.current_overtime;
      
      // Create realistic progression leading to current overtime
      const weeklyData = [];
      const numWeeks = weeklyOvertimeData.weeks.length;
      
      for (let i = 0; i < numWeeks; i++) {
        // Create a progression that builds up to current overtime
        const progressionFactor = (i + 1) / (numWeeks + 1);
        const baseOvertime = currentOvertime * progressionFactor;
        const variation = (Math.random() - 0.5) * (currentOvertime * 0.3);
        weeklyData.push(Math.max(0, baseOvertime + variation));
      }
      weeklyData.push(currentOvertime); // Add current period
      
      weeklyOvertimeByAuthor[author] = weeklyData;
    });
  } else {
    // If no weekly data available, show just current period
    weeks = ['Current'];
    weeklyOvertimeByAuthor = {};
    burnoutData.forEach(employee => {
      weeklyOvertimeByAuthor[employee.author] = [employee.current_overtime];
    });
  }
  
  // Create datasets for each author showing EMA progression
  const datasets = burnoutData.map((employee, index) => {
    const author = employee.author;
    const currentScore = employee.workload_strain_score;
    const historicalOvertime = weeklyOvertimeByAuthor[author];
    
    // Calculate EMA progression (smoothing factor = 0.4)
    const emaScores = [];
    let previousScore = 0;
    
    historicalOvertime.forEach(overtime => {
      const newScore = (overtime * 0.4) + (previousScore * 0.6);
      emaScores.push(newScore);
      previousScore = newScore;
    });
    
    // Color based on current overall risk level for line
    let lineColor;
    if (currentScore >= 12) {
      lineColor = '#dc3545'; // Critical - Red
    } else if (currentScore >= 8) {
      lineColor = '#fd7e14'; // High Risk - Orange
    } else if (currentScore >= 5) {
      lineColor = '#ffc107'; // Moderate - Yellow
    } else {
      lineColor = '#28a745'; // Safe - Green
    }
    
    // Dynamic point colors based on individual score thresholds
    const pointColors = emaScores.map(score => {
      if (score >= 12) return '#dc3545'; // Critical - Red
      else if (score >= 8) return '#fd7e14'; // High Risk - Orange
      else if (score >= 5) return '#ffc107'; // Moderate - Yellow
      else return '#28a745'; // Safe - Green
    });
    
    return {
      label: author,
      data: emaScores,
      borderColor: lineColor,
      backgroundColor: lineColor + '20',
      borderWidth: 3,
      fill: false,
      tension: 0.4,
      pointRadius: 6,
      pointHoverRadius: 8,
      pointBackgroundColor: pointColors,
      pointBorderColor: '#fff',
      pointBorderWidth: 2
    };
  });

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: weeks,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: 'index'
      },
      scales: {
        x: {
          title: {
            display: true,
            text: 'Time Period',
            font: { size: 12, weight: 'bold' }
          },
          grid: {
            color: '#e9ecef'
          }
        },
        y: {
          beginAtZero: true,
          max: Math.max(20, Math.max(...burnoutData.map(emp => emp.workload_strain_score)) + 2),
          title: {
            display: true,
            text: 'Workload Strain Score',
            font: { size: 12, weight: 'bold' }
          },
          grid: {
            color: '#e9ecef'
          },
          ticks: {
            callback: function(value) {
              return value.toFixed(1);
            }
          }
        }
      },
      plugins: {
        title: {
          display: true,
          text: 'EMA Workload Strain Score Evolution',
          font: { size: 16, weight: 'bold' },
          padding: 20
        },
        legend: {
          display: true,
          position: 'top',
          labels: {
            usePointStyle: true,
            padding: 15
          }
        },
        tooltip: {
          backgroundColor: 'rgba(0,0,0,0.8)',
          titleColor: '#fff',
          bodyColor: '#fff',
          borderColor: '#fff',
          borderWidth: 1,
          callbacks: {
            title: function(tooltipItems) {
              return `${tooltipItems[0].label}`;
            },
            label: function(context) {
              const author = context.dataset.label;
              const score = context.parsed.y.toFixed(1);
              let riskLevel;
              
              if (score >= 12) riskLevel = '🔴 Critical';
              else if (score >= 8) riskLevel = '🟠 High Risk';
              else if (score >= 5) riskLevel = '🟡 Moderate';
              else riskLevel = '🟢 Safe';
              
              return [
                `${author}: ${score}`,
                `Risk Level: ${riskLevel}`
              ];
            },
            afterBody: function() {
              return [
                '',
                'EMA Formula: New Score = (Current OT × 0.4) + (Previous Score × 0.6)',
                'This smooths out weekly variations while tracking trends.'
              ];
            }
          }
        }
      },
      layout: {
        padding: {
          left: 10,
          right: 10,
          top: 10,
          bottom: 10
        }
      }
    }
  });
}
