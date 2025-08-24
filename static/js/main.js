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
  localStorage.setItem("overtimeUIEnabled", checkbox.checked);
  if (checkbox.checked) {
    settingsToggle.style.display = "block";
    if (overtimeChart) overtimeChart.style.display = "block";
    if (overtimeBreakdown) overtimeBreakdown.style.display = "block";
  } else {
    settingsToggle.style.display = "none";
    if (overtimeChart) overtimeChart.style.display = "none";
    if (overtimeBreakdown) overtimeBreakdown.style.display = "none";
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
          label: "Overtime Hours",
          data: data.overtime_hours,
          backgroundColor: "rgba(255, 99, 132, 0.5)",
          borderColor: "rgb(255, 99, 132)",
          borderWidth: 1,
          barPercentage: 0.8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        title: {
          display: true,
          text: "Weekly Overtime Hours",
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
              return `Overtime: ${context.parsed.y.toFixed(2)} hours`;
            },
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: "Hours",
            font: { size: 12 },
          },
        },
        x: {
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
