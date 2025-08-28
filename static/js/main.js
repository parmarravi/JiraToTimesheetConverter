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
  paginationSummaryTable();
  const displayDiv = document.getElementById("date-display");
  const startDate = "{{ start_date }}";
  const endDate = "{{ end_date }}";

  if (displayDiv) {
    displayDiv.textContent = formatDateRange(startDate, endDate);
  }
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

  // const reportDownload = document.getElementById("reportButton");
  // if (reportDownload) {
  //   reportDownload.addEventListener("click", function () {
  //     downloadSectionPDF();
  //   });
  // }
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
  const savedStateAvailableCapacity = localStorage.getItem(
    "availableCapacityUIEnabled"
  );

  if (savedState === "true") {
    const checkbox = document.getElementById("showOvertimeUI");
    if (checkbox) {
      checkbox.checked = true;
      toggleOvertimeUI();
    }
  }

  if (savedStateAvailableCapacity === "true") {
    const checkboxAvailableCapacity = document.getElementById("showCapacityUI");
    if (checkboxAvailableCapacity) {
      checkboxAvailableCapacity.checked = true;
      toggleCapacityUI();
    }
  }
}
function preserveOvertimeState() {
  const checkbox = document.getElementById("showOvertimeUI");
  if (checkbox) {
    localStorage.setItem("overtimeUIEnabled", checkbox.checked);
  }

  const checkboxCapacityUI = document.getElementById("showCapacityUI");
  if (checkboxCapacityUI) {
    localStorage.setItem(
      "availableCapacityUIEnabled",
      checkboxCapacityUI.checked
    );
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
          position: "top",
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
    type: "doughnut", // change pie to doughnut
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
        legend: { position: "bottom" },
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
    cutout: "50%", // adjust donut thickness
    rotation: -90, // start angle
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

  if (
    weeklyOvertimeData &&
    weeklyOvertimeData.weeks &&
    weeklyOvertimeData.weeks.length > 0
  ) {
    weeks = [...weeklyOvertimeData.weeks, "Current"];

    // Extract weekly overtime data per author from the existing weekly chart data
    // For now, we'll distribute the weekly overtime equally among authors in that week
    // In a real implementation, this would come from the backend with per-author weekly breakdown
    weeklyOvertimeByAuthor = {};
    burnoutData.forEach((employee) => {
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
    weeks = ["Current"];
    weeklyOvertimeByAuthor = {};
    burnoutData.forEach((employee) => {
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

    historicalOvertime.forEach((overtime) => {
      const newScore = overtime * 0.4 + previousScore * 0.6;
      emaScores.push(newScore);
      previousScore = newScore;
    });

    // Color based on current overall risk level for line
    let lineColor;
    if (currentScore >= 12) {
      lineColor = "#dc3545"; // Critical - Red
    } else if (currentScore >= 8) {
      lineColor = "#fd7e14"; // High Risk - Orange
    } else if (currentScore >= 5) {
      lineColor = "#ffc107"; // Moderate - Yellow
    } else {
      lineColor = "#28a745"; // Safe - Green
    }

    // Dynamic point colors based on individual score thresholds
    const pointColors = emaScores.map((score) => {
      if (score >= 12) return "#dc3545"; // Critical - Red
      else if (score >= 8) return "#fd7e14"; // High Risk - Orange
      else if (score >= 5) return "#ffc107"; // Moderate - Yellow
      else return "#28a745"; // Safe - Green
    });

    return {
      label: author,
      data: emaScores,
      borderColor: lineColor,
      backgroundColor: lineColor + "20",
      borderWidth: 3,
      fill: false,
      tension: 0.4,
      pointRadius: 6,
      pointHoverRadius: 8,
      pointBackgroundColor: pointColors,
      pointBorderColor: "#fff",
      pointBorderWidth: 2,
    };
  });

  new Chart(ctx, {
    type: "line",
    data: {
      labels: weeks,
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: "index",
      },
      scales: {
        x: {
          title: {
            display: true,
            text: "Time Period",
            font: { size: 12, weight: "bold" },
          },
          grid: {
            color: "#e9ecef",
          },
        },
        y: {
          beginAtZero: true,
          max: Math.max(
            20,
            Math.max(...burnoutData.map((emp) => emp.workload_strain_score)) + 2
          ),
          title: {
            display: true,
            text: "Workload Strain Score",
            font: { size: 12, weight: "bold" },
          },
          grid: {
            color: "#e9ecef",
          },
          ticks: {
            callback: function (value) {
              return value.toFixed(1);
            },
          },
        },
      },
      plugins: {
        title: {
          display: true,
          text: "EMA Workload Strain Score Evolution",
          font: { size: 16, weight: "bold" },
          padding: 20,
        },
        legend: {
          display: true,
          position: "top",
          labels: {
            usePointStyle: true,
            padding: 15,
          },
        },
        tooltip: {
          backgroundColor: "rgba(0,0,0,0.8)",
          titleColor: "#fff",
          bodyColor: "#fff",
          borderColor: "#fff",
          borderWidth: 1,
          callbacks: {
            title: function (tooltipItems) {
              return `${tooltipItems[0].label}`;
            },
            label: function (context) {
              const author = context.dataset.label;
              const score = context.parsed.y.toFixed(1);
              let riskLevel;

              if (score >= 12) riskLevel = "🔴 Critical";
              else if (score >= 8) riskLevel = "🟠 High Risk";
              else if (score >= 5) riskLevel = "🟡 Moderate";
              else riskLevel = "🟢 Safe";

              return [`${author}: ${score}`, `Risk Level: ${riskLevel}`];
            },
            afterBody: function () {
              return [
                "",
                "EMA Formula: New Score = (Current OT × 0.4) + (Previous Score × 0.6)",
                "This smooths out weekly variations while tracking trends.",
              ];
            },
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

function paginationSummaryTable() {
  const rows = document.querySelectorAll("#summary-table tbody tr");
  const rowsPerPage = 10;
  const totalRows = rows.length;
  const totalPages = Math.ceil(totalRows / rowsPerPage);
  const info = document.getElementById("summary-info");
  const controls = document.getElementById("pagination-controls");

  let currentPage = 1;

  function renderTable(page) {
    const start = (page - 1) * rowsPerPage;
    const end = start + rowsPerPage;

    rows.forEach((row, index) => {
      row.style.display = index >= start && index < end ? "" : "none";
    });

    info.textContent = `Showing ${Math.min(start + 1, totalRows)}–${Math.min(
      end,
      totalRows
    )} of ${totalRows} entries`;

    renderControls();
  }

  function renderControls() {
    controls.innerHTML = "";
    for (let i = 1; i <= totalPages; i++) {
      const btn = document.createElement("button");
      btn.textContent = i;
      btn.className = i === currentPage ? "active" : "";
      btn.addEventListener("click", () => {
        currentPage = i;
        renderTable(currentPage);
      });
      controls.appendChild(btn);
    }
  }

  renderTable(currentPage);
}
// async function convertCanvasesToImages(container) {
//   const canvases = container.querySelectorAll("canvas");

//   for (const canvas of canvases) {
//     try {
//       // Ensure chart is rendered before capturing
//       await new Promise((r) => requestAnimationFrame(r));

//       const imgData = canvas.toDataURL("image/png");

//       const img = document.createElement("img");
//       img.src = imgData;
//       img.style.maxWidth = "100%"; // scale nicely in PDF
//       img.style.height = "auto";

//       // Replace the canvas with the static image
//       canvas.replaceWith(img);
//     } catch (err) {
//       console.error("Error converting canvas:", err, canvas);
//     }
//   }
// }

function replaceCanvasWithImages(container) {
  // Find all canvas elements inside the section
  const canvases = container.querySelectorAll("canvas");

  canvases.forEach((canvas) => {
    try {
      // Convert canvas to image
      let imgData = canvas.toDataURL("image/png");
      let img = document.createElement("img");
      img.src = imgData;
      img.width = canvas.width;
      img.height = canvas.height;

      // Replace canvas with the image
      canvas.replaceWith(img);
    } catch (err) {
      console.error("Error converting canvas:", err, canvas);
    }
  });
}

async function convertCanvasesToImages(container) {
  const canvases = container.querySelectorAll("canvas");

  for (const canvas of canvases) {
    try {
      await new Promise((r) => requestAnimationFrame(r)); // wait for chart render
      const imgData = canvas.toDataURL("image/png");
      const img = document.createElement("img");
      img.src = imgData;
      img.style.maxWidth = "100%";
      img.style.height = "auto";
      canvas.replaceWith(img);
    } catch (err) {
      console.error("Error converting canvas:", err, canvas);
    }
  }
}

function forceSectionNewPage(sectionId) {
  const section = document.getElementById(sectionId);
  if (section) {
    section.classList.add("page-break-before");
  }
}
async function downloadSectionPDF() {
  console.log("Starting PDF generation...");
  const element = document.getElementById("reportSection");

  // Load saved states from localStorage
  const savedStateOverTime = localStorage.getItem("overtimeUIEnabled");
  const savedStateCapacityUi = localStorage.getItem(
    "availableCapacityUIEnabled"
  );

  console.log(
    "Saved States - Overtime:",
    savedStateOverTime,
    "Capacity UI:",
    savedStateCapacityUi
  );

  await convertCanvasesToImages(element);

  // Clone the element
  const clone = element.cloneNode(true);

  // Expand all rows in clone
  const cloneRows = clone.querySelectorAll("#summary-table tbody tr");
  cloneRows.forEach((row) => (row.style.display = "")); // show all rows

  // Replace canvases in clone with images
  await convertCanvasesToImages(clone);

  // Results section page break (only when capacity is true)
  if (savedStateCapacityUi === "true") {
    const resultsSection = clone.querySelector("#results-container");
    if (resultsSection) {
      resultsSection.classList.add("page-break-before");
    }
  }

  // Overtime section page break (only if exactly one of them is true)
  if ((savedStateCapacityUi === "true") !== (savedStateOverTime === "true")) {
    const overtimeSection = clone.querySelector("#overtimeSection");
    if (overtimeSection) {
      overtimeSection.classList.add("page-break-before");
    }
  }

  // Summary section page break (only if capacity true and overtime false)
  if (savedStateCapacityUi !== "true" && savedStateOverTime === "false") {
    const sectionSummaryInClone = clone.querySelector("#summary-container");
    if (sectionSummaryInClone) {
      sectionSummaryInClone.classList.add("page-break-before");
    }
  }

  // Hide pagination in the clone
  const paginationInClone = clone.querySelector("#pagination-controls");
  if (paginationInClone) paginationInClone.style.display = "none";

  // Hide clone but keep measurable
  // clone.style.position = "absolute";
  // clone.style.top = "0";
  // clone.style.left = "0";
  // clone.style.width = "100%";
  // clone.style.visibility = "hidden";

  // Hidden wrapper
  const wrapper = document.createElement("div");
  wrapper.style.position = "fixed";
  wrapper.style.top = "0";
  wrapper.style.left = "0";
  wrapper.style.width = "100%";
  wrapper.style.background = "#fff";
  wrapper.style.zIndex = "-1";
  wrapper.style.visibility = "hidden";

  wrapper.appendChild(clone);
  document.body.appendChild(wrapper);

  const opt = {
    margin: 0.3,
    filename: "report.pdf",
    image: { type: "jpeg", quality: 0.98 },
    html2canvas: { scale: 2, logging: true, useCORS: true, scrollY: 0 },
    jsPDF: { unit: "in", format: "a4", orientation: "portrait" },
  };

  try {
    await html2pdf().set(opt).from(clone).save();
    console.log("PDF generated successfully");
  } catch (err) {
    console.error("Error in PDF generation:", err);
  } finally {
    document.body.removeChild(wrapper);
  }
}

function toggleCapacityUI() {
  console.log("Toggling Capacity UI");
  const section = document.getElementById("capacityTableSection");
  const toggle = document.getElementById("showCapacityUI");
  section.style.display = toggle.checked ? "block" : "none";
  localStorage.setItem("availableCapacityUIEnabled", toggle.checked);
}

function initProjectNameDisplay(
  projectInputId = "project_name",
  projectDisplayId = "project_display"
) {
  const projectInput = document.getElementById(projectInputId);
  const projectDisplay = document.getElementById(projectDisplayId);

  if (!projectInput || !projectDisplay) return;

  projectInput.addEventListener("input", () => {
    projectDisplay.textContent =
      projectInput.value || projectInput.defaultValue;
  });
}

function initLogoUpload(
  logoInputId = "project_logo",
  logoPreviewId = "logo_preview"
) {
  const logoInput = document.getElementById(logoInputId);
  const logoPreview = document.getElementById(logoPreviewId);

  if (!logoInput || !logoPreview) return;

  logoInput.addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        logoPreview.src = e.target.result;
      };
      reader.readAsDataURL(file);
    }
  });

  logoPreview.addEventListener("click", () => {
    logoInput.click();
  });
}

function formatDateRange(startDate, endDate) {
  function formatDate(dateStr) {
    const parts = dateStr.split("-"); // YYYY-MM-DD
    return parts[2] + "/" + parts[1] + "/" + parts[0];
  }
  if (startDate && endDate)
    return formatDate(startDate) + " To " + formatDate(endDate);
  if (startDate) return "From " + formatDate(startDate);
  if (endDate) return "Up to " + formatDate(endDate);
  return "No date range selected";
}
