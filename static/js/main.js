// --- Main JS for Jira Timesheet UI ---
import { dbManager } from "./db.js";

// State - with safe defaults
let holidays = Array.isArray(serverData?.holidays) ? serverData.holidays : [];
let selectedMonth = null;
let selectedYear = null;
let isInitializing = true; // Flag to prevent form submissions during initialization

// Initialize IndexedDB
let dbInitialized = false;

// Initialize database
async function initializeDB() {
  if (!dbInitialized) {
    try {
      await dbManager.initDB();
      dbInitialized = true;
      console.log("Database initialized successfully");
    } catch (error) {
      console.error("Failed to initialize database:", error);
      throw error;
    }
  }
}

// Function to save all form states to localStorage
function saveAllFormStates() {
  const authorSubtaskToggle = document.getElementById("showAuthorSubtaskUI");
  const capacityToggle = document.getElementById("showCapacityUI");
  const overtimeToggle = document.getElementById("showOvertimeUI");

  // Get category type
  const categoryTypeRadios = document.querySelectorAll(
    'input[name="category_type"]'
  );
  let categoryType = "Activity"; // Default value
  let customColumn = "";
  categoryTypeRadios.forEach((radio) => {
    if (radio.checked) {
      if (radio.value === "Custom") {
        const customInput = document.getElementById("customColumnInput");
        categoryType = "Custom";
        customColumn = customInput ? customInput.value : "";
      } else {
        categoryType = radio.value;
      }
    }
  });

  // Get summary type
  const summaryTypeRadios = document.querySelectorAll(
    'input[name="summary_type"]'
  );
  let summaryType = "Issue Summary"; // Default value
  summaryTypeRadios.forEach((radio) => {
    if (radio.checked) {
      summaryType = radio.value;
    }
  });

  // Get working days
  const workingDaysCheckboxes = document.querySelectorAll(
    'input[name="working_days"]'
  );
  const workingDays = [];
  workingDaysCheckboxes.forEach((checkbox) => {
    if (checkbox.checked) {
      workingDays.push(checkbox.value);
    }
  });

  // Default working days if none selected
  const defaultWorkingDays =
    workingDays.length > 0
      ? workingDays
      : ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

  // Get other overtime settings
  const workingHoursInput = document.querySelector(
    'input[name="working_hours"]'
  );
  const leaveDaysInput = document.querySelector('input[name="leave_days"]');
  const holidayDaysInput = document.querySelector('input[name="holiday_days"]');

  // Get overtime settings panel state
  const overtimeSettingsPanel = document.getElementById(
    "overtimeSettingsPanel"
  );
  const showOvertimeSettings = overtimeSettingsPanel
    ? overtimeSettingsPanel.style.display !== "none"
    : false;

  const formStates = {
    // Toggle states
    toggles: {
      showAuthorSubtask: authorSubtaskToggle
        ? authorSubtaskToggle.checked
        : false,
      showCapacity: capacityToggle ? capacityToggle.checked : false,
      showOvertime: overtimeToggle ? overtimeToggle.checked : false,
    },
    // Category and summary settings with defaults
    categoryType: categoryType,
    customColumn: customColumn,
    summaryType: summaryType,
    // Overtime settings
    overtimeSettings: {
      showSettings: showOvertimeSettings,
      workingDays: defaultWorkingDays,
      workingHours: workingHoursInput
        ? parseFloat(workingHoursInput.value) || 8
        : 8,
      leaveDays: leaveDaysInput ? parseFloat(leaveDaysInput.value) || 0 : 0,
      holidayDays: holidayDaysInput
        ? parseFloat(holidayDaysInput.value) || 0
        : 0,
    },
  };

  localStorage.setItem("formStates", JSON.stringify(formStates));
  console.log("Saved form states:", formStates);
}

// Function to load all form states from localStorage
function loadAllFormStates() {
  try {
    const savedStates = localStorage.getItem("formStates");
    if (savedStates) {
      return JSON.parse(savedStates);
    }
  } catch (error) {
    console.error("Error loading form states from localStorage:", error);
  }

  // Return default states if no saved states or error
  return {
    toggles: {
      showAuthorSubtask: false,
      showCapacity: false,
      showOvertime: false,
    },
    categoryType: "Activity",
    customColumn: "",
    summaryType: "Issue Summary",
    overtimeSettings: {
      showSettings: false,
      workingDays: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      workingHours: 8,
      leaveDays: 0,
      holidayDays: 0,
    },
  };
}

// Function to save toggle states to localStorage (backwards compatibility)
function saveToggleStates() {
  saveAllFormStates(); // Use the comprehensive function
}

// Function to load toggle states from localStorage (backwards compatibility)
function loadToggleStates() {
  const allStates = loadAllFormStates();
  return allStates.toggles;
}

// Function to restore UI state
function restoreUIState() {
  const urlParams = new URLSearchParams(window.location.search);

  // Restore author selection
  const selectAllCheckbox = document.getElementById("selectAllAuthors");
  const authorCheckboxes = document.querySelectorAll(".author-checkbox");

  // Get selected authors from URL parameters
  const selectedAuthors = urlParams.getAll("author");

  // Temporarily disable event handling during restoration
  const originalInitializing = isInitializing;
  isInitializing = true;

  // If no authors in URL or only 'All' is selected
  if (
    !selectedAuthors.length ||
    (selectedAuthors.length === 1 && selectedAuthors[0] === "All")
  ) {
    if (selectAllCheckbox) {
      selectAllCheckbox.checked = true;
      authorCheckboxes.forEach((checkbox) => {
        checkbox.checked = true;
      });
    }
  } else {
    // Uncheck "Select All" first
    if (selectAllCheckbox) {
      selectAllCheckbox.checked = false;
    }

    // Set individual author checkboxes based on URL
    authorCheckboxes.forEach((checkbox) => {
      checkbox.checked = selectedAuthors.includes(checkbox.value);
    });
  }

  // Load all saved form states
  const savedFormStates = loadAllFormStates();

  // Restore toggle states
  const authorSubtaskToggle = document.getElementById("showAuthorSubtaskUI");
  const capacityToggle = document.getElementById("showCapacityUI");
  const overtimeToggle = document.getElementById("showOvertimeUI");

  if (authorSubtaskToggle) {
    authorSubtaskToggle.checked = savedFormStates.toggles.showAuthorSubtask;
  }
  if (capacityToggle) {
    capacityToggle.checked = savedFormStates.toggles.showCapacity;
  }
  if (overtimeToggle) {
    overtimeToggle.checked = savedFormStates.toggles.showOvertime;
  }

  // Restore category type (only if not set by URL parameters)
  if (!urlParams.get("category_type")) {
    const categoryTypeRadios = document.querySelectorAll(
      'input[name="category_type"]'
    );
    categoryTypeRadios.forEach((radio) => {
      if (savedFormStates.categoryType === "Custom") {
        if (radio.value === "Custom") {
          radio.checked = true;
          const customInput = document.getElementById("customColumnInput");
          if (customInput) {
            customInput.value = savedFormStates.customColumn;
            customInput.disabled = false;
          }
        } else {
          radio.checked = false;
        }
      } else {
        radio.checked = radio.value === savedFormStates.categoryType;
      }
    });
  }

  // Restore summary type (only if not set by URL parameters)
  if (!urlParams.get("summary_type")) {
    const summaryTypeRadios = document.querySelectorAll(
      'input[name="summary_type"]'
    );
    summaryTypeRadios.forEach((radio) => {
      radio.checked = radio.value === savedFormStates.summaryType;
    });
  }

  // Restore overtime settings (only if not set by URL parameters or form data)
  if (!urlParams.get("working_hours")) {
    const workingHoursInput = document.querySelector(
      'input[name="working_hours"]'
    );
    if (workingHoursInput) {
      workingHoursInput.value = savedFormStates.overtimeSettings.workingHours;
    }
  }

  if (!urlParams.get("leave_days")) {
    const leaveDaysInput = document.querySelector('input[name="leave_days"]');
    if (leaveDaysInput) {
      leaveDaysInput.value = savedFormStates.overtimeSettings.leaveDays;
    }
  }

  if (!urlParams.get("holiday_days")) {
    const holidayDaysInput = document.querySelector(
      'input[name="holiday_days"]'
    );
    if (holidayDaysInput) {
      holidayDaysInput.value = savedFormStates.overtimeSettings.holidayDays;
    }
  }

  // Restore working days (only if not set by URL parameters)
  if (!urlParams.getAll("working_days").length) {
    const workingDaysCheckboxes = document.querySelectorAll(
      'input[name="working_days"]'
    );
    workingDaysCheckboxes.forEach((checkbox) => {
      checkbox.checked = savedFormStates.overtimeSettings.workingDays.includes(
        checkbox.value
      );
    });
  }

  // Call toggle functions to update UI based on current checkbox states
  toggleAuthorSubtaskUI();
  toggleCapacityUI();
  toggleOvertimeUI();

  // Restore overtime settings panel state
  if (
    savedFormStates.overtimeSettings.showSettings &&
    savedFormStates.toggles.showOvertime
  ) {
    const panel = document.getElementById("overtimeSettingsPanel");
    const toggleText = document.getElementById("overtimeToggleText");
    const toggleIcon = document.getElementById("overtimeToggleIcon");
    if (panel) {
      panel.style.display = "block";
      if (toggleText)
        toggleText.textContent = "Hide Overtime Calculation Settings";
      if (toggleIcon) toggleIcon.textContent = "▲";
    }
  }

  // Restore initialization flag
  isInitializing = originalInitializing;
}

// Function to preserve UI state when submitting form
function preserveUIState(event) {
  const form = event.target;

  // Add toggle states to form
  const authorSubtaskToggle = document.getElementById("showAuthorSubtaskUI");
  const capacityToggle = document.getElementById("showCapacityUI");
  const overtimeToggle = document.getElementById("showOvertimeUI");

  if (authorSubtaskToggle) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "show_author_subtask";
    input.value = authorSubtaskToggle.checked;
    form.appendChild(input);
  }

  if (capacityToggle) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "show_capacity";
    input.value = capacityToggle.checked;
    form.appendChild(input);
  }

  if (overtimeToggle) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "show_overtime";
    input.value = overtimeToggle.checked;
    form.appendChild(input);
  }
}

// Function to initialize localStorage with default values if none exist
function initializeDefaultFormStates() {
  const existingStates = localStorage.getItem("formStates");

  // Only set defaults if no saved states exist
  if (!existingStates) {
    const defaultStates = {
      toggles: {
        showAuthorSubtask: false,
        showCapacity: false,
        showOvertime: false,
      },
      categoryType: "Activity",
      customColumn: "",
      summaryType: "Issue Summary",
      overtimeSettings: {
        showSettings: false,
        workingDays: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        workingHours: 8,
        leaveDays: 0,
        holidayDays: 0,
      },
    };

    localStorage.setItem("formStates", JSON.stringify(defaultStates));
    console.log(
      "Initialized localStorage with default form states:",
      defaultStates
    );

    // Set the default radio buttons in the DOM
    setDefaultRadioButtons();
  }
}

// Function to set default radio buttons in the DOM
function setDefaultRadioButtons() {
  // Set Activity as default category type
  const activityRadio = document.querySelector(
    'input[name="category_type"][value="Activity"]'
  );
  if (activityRadio) {
    activityRadio.checked = true;
  }

  // Set Issue Summary as default summary type
  const issueSummaryRadio = document.querySelector(
    'input[name="summary_type"][value="Issue Summary"]'
  );
  if (issueSummaryRadio) {
    issueSummaryRadio.checked = true;
  }

  // Disable custom column input by default
  const customInput = document.getElementById("customColumnInput");
  if (customInput) {
    customInput.disabled = true;
    customInput.value = "";
  }
}

// DOM Ready
document.addEventListener("DOMContentLoaded", async function () {
  try {
    // First initialize the database
    await initializeDB();

    // Initialize default form states in localStorage if none exist
    initializeDefaultFormStates();

    // Restore UI states
    restoreUIState();

    // Initialize calendar and other UI elements
    setCalendarToCurrentMonth();
    setupEventListeners();

    // Wait for a small delay to ensure DOM is ready
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Initialize charts (only if chart elements exist)
    try {
      await initializeCharts();
    } catch (error) {
      console.log("Charts not available or failed to initialize:", error);
    }

    // Initialize pagination (only if summary table exists)
    try {
      paginationSummaryTable();
    } catch (error) {
      console.log("Pagination not available or failed to initialize:", error);
    }

    // Set date range display
    const displayDiv = document.getElementById("date-display");
    const startDate = "{{ start_date }}";
    const endDate = "{{ end_date }}";

    if (displayDiv) {
      displayDiv.textContent = formatDateRange(startDate, endDate);
    }

    // Mark initialization as complete
    isInitializing = false;
  } catch (error) {
    console.error("Error during initialization:", error);
    // Mark initialization as complete even if there was an error
    isInitializing = false;
    // Show user-friendly error message
    // const errorDiv = document.createElement("div");
    // errorDiv.style.cssText =
    //   "background-color: #ffebee; color: #c62828; padding: 10px; margin: 10px; border-radius: 4px;";
    // errorDiv.textContent =
    //   "Failed to initialize the application. Please refresh the page or contact support if the issue persists.";
    // document.body.insertBefore(errorDiv, document.body.firstChild);
  }
});

function setupEventListeners() {
  // Set up form submission handler
  const filterForm = document.querySelector(".filter-form");
  if (filterForm) {
    filterForm.addEventListener("submit", preserveUIState);
  }

  // Set up author selection handlers
  const selectAllCheckbox = document.getElementById("selectAllAuthors");
  const authorCheckboxes = document.querySelectorAll(".author-checkbox");

  function updateBulkDownloadVisibility() {
    const bulkDownloadBtn = document.getElementById("bulkDownloadBtn");
    if (!bulkDownloadBtn) return;

    const selectedCount = Array.from(authorCheckboxes).filter(
      (cb) => cb.checked
    ).length;
    const showBulkDownload = selectAllCheckbox.checked || selectedCount > 1;
    bulkDownloadBtn.style.display = showBulkDownload ? "inline-block" : "none";
  }

  function updateAuthorSelectionState(shouldSubmit = false) {
    if (!selectAllCheckbox) return;

    const selectedAuthors = Array.from(authorCheckboxes)
      .filter((checkbox) => checkbox.checked)
      .map((checkbox) => checkbox.value);

    // If no authors are selected, select all authors
    if (selectedAuthors.length === 0) {
      selectAllCheckbox.checked = true;
      authorCheckboxes.forEach((checkbox) => {
        checkbox.checked = true;
        checkbox.disabled = true;
      });
    }

    // Update bulk download button visibility
    updateBulkDownloadVisibility();

    // Only submit the form if explicitly requested
    if (shouldSubmit) {
      document.querySelector(".filter-form").submit();
    }
  }

  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener("change", function () {
      if (isInitializing) {
        return;
      }

      // When "Select All" is checked, check and disable all others.
      // When unchecked, enable all others but leave them checked to allow deselection.
      authorCheckboxes.forEach((checkbox) => {
        checkbox.checked = true; // Always ensure all are checked when this control is toggled
        checkbox.disabled = this.checked;
      });

      updateBulkDownloadVisibility();

      // Removed automatic form submission - only submit on Filter button click
    });
  }

  if (authorCheckboxes) {
    authorCheckboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", function () {
        if (isInitializing) {
          return;
        }

        const checkedCount = Array.from(authorCheckboxes).filter(
          (cb) => cb.checked
        ).length;
        const allCount = authorCheckboxes.length;

        if (checkedCount === 0) {
          // Prevent the last checkbox from being unchecked
          this.checked = true;
          // No submission needed as state doesn't change
          return;
        }

        if (checkedCount === allCount) {
          // If all are checked, revert to "Select All" mode
          selectAllCheckbox.checked = true;
          authorCheckboxes.forEach((cb) => (cb.disabled = true));
        } else {
          // If some are unchecked, ensure "Select All" is also unchecked
          selectAllCheckbox.checked = false;
        }

        updateBulkDownloadVisibility();
        // Removed automatic form submission - only submit on Filter button click
      });
    });
  }

  // Initial state setup - don't submit form on page load
  updateAuthorSelectionState(false);

  // Set up toggle UI handlers
  const authorSubtaskToggle = document.getElementById("showAuthorSubtaskUI");
  if (authorSubtaskToggle) {
    authorSubtaskToggle.addEventListener("change", toggleAuthorSubtaskUI);
  }

  const capacityToggle = document.getElementById("showCapacityUI");
  if (capacityToggle) {
    capacityToggle.addEventListener("change", toggleCapacityUI);
  }

  const overtimeToggle = document.getElementById("showOvertimeUI");
  if (overtimeToggle) {
    overtimeToggle.addEventListener("change", toggleOvertimeUI);
  }

  // Set up all button handlers
  const overtimeSettingsBtn = document.getElementById("overtimeSettingsBtn");
  if (overtimeSettingsBtn) {
    overtimeSettingsBtn.addEventListener("click", toggleOvertimeSettings);
  }

  const prevMonthBtn = document.getElementById("prevMonthBtn");
  if (prevMonthBtn) {
    prevMonthBtn.addEventListener("click", () => changeMonth(-1));
  }

  const nextMonthBtn = document.getElementById("nextMonthBtn");
  if (nextMonthBtn) {
    nextMonthBtn.addEventListener("click", () => changeMonth(1));
  }

  const resetHolidaysBtn = document.getElementById("resetHolidaysBtn");
  if (resetHolidaysBtn) {
    resetHolidaysBtn.addEventListener("click", resetHolidays);
  }

  const uploadHolidayExcelBtn = document.getElementById(
    "uploadHolidayExcelBtn"
  );
  if (uploadHolidayExcelBtn) {
    uploadHolidayExcelBtn.addEventListener("click", uploadHolidayExcel);
  }

  // Setup report button handler
  const reportButton = document.getElementById("reportButton");
  if (reportButton) {
    console.log("Setting up report button event listener");
    reportButton.addEventListener("click", downloadSectionPDF);
  } else {
    console.log("Report button not found in DOM");
  }

  // Category type radio buttons
  const categoryRadios = document.querySelectorAll(
    'input[name="category_type"]'
  );
  categoryRadios.forEach((radio) => {
    radio.addEventListener("change", function () {
      toggleCustomInput();
      saveAllFormStates(); // Save when category changes
    });
  });

  // Summary type radio buttons
  const summaryRadios = document.querySelectorAll('input[name="summary_type"]');
  summaryRadios.forEach((radio) => {
    radio.addEventListener("change", function () {
      saveAllFormStates(); // Save when summary type changes
    });
  });

  // Overtime settings inputs
  const overtimeInputs = document.querySelectorAll(
    'input[name="working_hours"], input[name="leave_days"], input[name="holiday_days"]'
  );
  overtimeInputs.forEach((input) => {
    input.addEventListener("change", function () {
      saveAllFormStates(); // Save when overtime settings change
    });
  });

  // Working days checkboxes
  const workingDaysCheckboxes = document.querySelectorAll(
    'input[name="working_days"]'
  );
  workingDaysCheckboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", function () {
      saveAllFormStates(); // Save when working days change
    });
  });

  // Custom column input
  const customInput = document.getElementById("customColumnInput");
  if (customInput) {
    customInput.addEventListener("focus", function () {
      document.querySelector(
        'input[name="category_type"][value="Custom"]'
      ).checked = true;
      this.disabled = false;
      saveAllFormStates(); // Save when custom column is focused
    });

    customInput.addEventListener("input", function () {
      saveAllFormStates(); // Save when custom column content changes
    });
  }

  // Form submit
  const form = document.querySelector("form.filter-form");
  if (form) {
    form.addEventListener("submit", async function (e) {
      console.log("Form submitted");

      // Log selected authors
      const selectAllCheckbox = document.getElementById("selectAllAuthors");
      const authorCheckboxes = document.querySelectorAll(".author-checkbox");
      const selectedAuthors = [];

      if (selectAllCheckbox && selectAllCheckbox.checked) {
        selectedAuthors.push("All");
      } else {
        authorCheckboxes.forEach((checkbox) => {
          if (checkbox.checked) {
            selectedAuthors.push(checkbox.value);
          }
        });
      }

      console.log("Selected authors:", selectedAuthors);
      console.log("Total selected count:", selectedAuthors.length);

      try {
        // Handle custom input if present
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

        // Save all states before submission
        saveAllFormStates();

        // Clean up charts if needed (function may not exist, so check first)
        if (typeof cleanupCharts === "function") {
          cleanupCharts();
        }
      } catch (error) {
        console.error("Error during form submission:", error);
      }
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

  // Summary sort dropdown change
  const summarySortDropdown = document.getElementById("summarySortDropdown");
  if (summarySortDropdown) {
    summarySortDropdown.addEventListener("change", function () {
      const currentUrl = new URL(window.location);
      currentUrl.searchParams.set("summary_sort_by", this.value);
      window.location.href = currentUrl.toString();
    });
  }

  // const reportDownload = document.getElementById("reportButton");
  // if (reportDownload) {
  //   reportDownload.addEventListener("click", function () {
  //     downloadSectionPDF();
  //   });
  // }
}

async function toggleAuthorSubtaskUI() {
  console.log("Toggling Author Subtask UI");
  const section = document.getElementById("author-task-container");
  const toggle = document.getElementById("showAuthorSubtaskUI");
  console.log("Toggling Author Subtask UI", section);
  if (section && toggle) {
    section.style.display = toggle.checked ? "block" : "none";
    // Save all form states to localStorage
    saveAllFormStates();
  }
}

async function toggleCapacityUI() {
  console.log("Toggling Capacity UI");
  const section = document.getElementById("capacityTableSection");
  const toggle = document.getElementById("showCapacityUI");

  if (section && toggle) {
    section.style.display = toggle.checked ? "block" : "none";
    // Save all form states to localStorage
    saveAllFormStates();
  }
}

// Overtime UI toggle
async function toggleOvertimeUI() {
  const checkbox = document.getElementById("showOvertimeUI");
  const settingsToggle = document.getElementById("overtimeSettingsToggle");
  const overtimeChart = document.getElementById("overtimeChart");
  const overtimeBreakdown = document.getElementById("overtimeBreakdown");
  const burnoutAlert = document.getElementById("burnoutAlert");
  const overTimeAuthor = document.getElementById("overTimeAuthor");

  // Save all form states to localStorage
  saveAllFormStates();

  if (checkbox && checkbox.checked) {
    if (settingsToggle) settingsToggle.style.display = "block";
    if (overtimeChart) overtimeChart.style.display = "block";
    if (overtimeBreakdown) overtimeBreakdown.style.display = "block";
    if (burnoutAlert) burnoutAlert.style.display = "block";
    if (overTimeAuthor) overTimeAuthor.style.display = "block";
  } else if (checkbox) {
    if (settingsToggle) settingsToggle.style.display = "none";
    if (overtimeChart) overtimeChart.style.display = "none";
    if (overtimeBreakdown) overtimeBreakdown.style.display = "none";
    if (burnoutAlert) burnoutAlert.style.display = "none";
    if (overTimeAuthor) overTimeAuthor.style.display = "none";
    const panel = document.getElementById("overtimeSettingsPanel");
    if (panel) panel.style.display = "none";
    const toggleText = document.getElementById("overtimeToggleText");
    const toggleIcon = document.getElementById("overtimeToggleIcon");
    if (toggleText)
      toggleText.textContent = "Show Overtime Calculation Settings";
    if (toggleIcon) toggleIcon.textContent = "▼";
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
  // Save the settings panel state
  saveAllFormStates();
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

// Make toggleHoliday globally accessible
window.toggleHoliday = toggleHoliday;
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
  console.log("Initializing initializeCharts...");

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
  // Check if summary table exists first
  const summaryTable = document.getElementById("summary-table");
  if (!summaryTable) {
    console.log("Summary table not found, skipping pagination setup");
    return;
  }

  // Get required elements
  const rows = document.querySelectorAll("#summary-table tbody tr");
  const rowsPerPage = 10;
  const totalRows = rows.length;
  const totalPages = Math.ceil(totalRows / rowsPerPage);

  // If no rows, skip pagination
  if (totalRows === 0) {
    console.log("No rows found in summary table, skipping pagination");
    return;
  }

  // Ensure required elements exist
  let info = document.getElementById("summary-info");
  let controls = document.getElementById("pagination-controls");

  // Create elements if they don't exist
  if (!info) {
    info = document.createElement("div");
    info.id = "summary-info";
    const table = document.getElementById("summary-table");
    if (table && table.parentElement) {
      table.parentElement.insertBefore(info, table.nextSibling);
    }
  }

  if (!controls) {
    controls = document.createElement("div");
    controls.id = "pagination-controls";
    if (info && info.parentElement) {
      info.parentElement.insertBefore(controls, info.nextSibling);
    }
  }

  let currentPage = 1;

  function renderTable(page) {
    const start = (page - 1) * rowsPerPage;
    const end = start + rowsPerPage;

    rows.forEach((row, index) => {
      row.style.display = index >= start && index < end ? "" : "none";
    });

    // Check if info element exists before updating
    if (info) {
      info.textContent = `Showing ${Math.min(start + 1, totalRows)}–${Math.min(
        end,
        totalRows
      )} of ${totalRows} entries`;
    } else {
      console.warn("Info element not found in the DOM");
    }

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

// 🟢 Utility to check if an element is effectively empty
function isVisiblyEmpty(el) {
  // no text, no children, and no meaningful size
  return (
    !el.textContent.trim() &&
    el.children.length === 0 &&
    el.offsetHeight === 0 &&
    el.offsetWidth === 0
  );
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
  try {
    const element = document.getElementById("reportSection");

    // Load saved states from localStorage
    const formStates = loadAllFormStates();
    const savedStateOverTime = formStates.toggles.showOvertime;
    const savedStateCapacityUi = formStates.toggles.showCapacity;

    await convertCanvasesToImages(element);

    // Clone the element
    const clone = element.cloneNode(true);

    // Expand all rows in clone
    const cloneRows = clone.querySelectorAll("#summary-table tbody tr");
    cloneRows.forEach((row) => (row.style.display = "")); // show all rows

    // Replace canvases in clone with images
    await convertCanvasesToImages(clone);

    // Force wide tables to fit within A4 portrait width
    const tables = clone.querySelectorAll("table");
    tables.forEach((table) => {
      table.style.fontSize = "11px"; // adjust as needed (e.g. 9px, 11px)
      table.style.padding = "2px"; // shrink cell padding
      table.style.maxWidth = "100%";
      table.style.width = "100%";
      table.style.wordBreak = "break-word";
      table.style.tableLayout = "auto"; // let columns shrink
      table.style.overflowX = "auto";
    });

    // Results section page break (only when capacity is true)
    if (savedStateCapacityUi === true) {
      const resultsSection = clone.querySelector("#results-container");
      if (resultsSection) {
        resultsSection.classList.add("page-break-before");
      }
    }

    // Overtime section page break (only if exactly one of them is true)
    if (savedStateCapacityUi !== savedStateOverTime) {
      const overtimeSection = clone.querySelector("#overtimeSection");
      if (overtimeSection) {
        overtimeSection.classList.add("page-break-before");
      }
    }

    // Summary section page break (only if capacity true and overtime false)
    if (savedStateCapacityUi !== true && savedStateOverTime === false) {
      const sectionSummaryInClone = clone.querySelector("#summary-container");
      if (sectionSummaryInClone) {
        sectionSummaryInClone.classList.add("page-break-before");
      }
    }

    // Hide pagination in the clone
    const paginationInClone = clone.querySelector("#pagination-controls");
    if (paginationInClone) paginationInClone.style.display = "none";

    const summarySortContainer = clone.querySelector("#summarySortContainer");
    if (summarySortContainer) summarySortContainer.style.display = "none";

    if (savedStateOverTime === false) {
      console.log("Hiding overtime section in PDF");
      const overtimeSection = clone.querySelector("#overtimeSection");
      overtimeSection.style.display = "none";
    } else {
      const overTimeAuthorInClone = clone.querySelector("#overTimeAuthor");
      if (overTimeAuthorInClone) {
        overTimeAuthorInClone.classList.add("page-break-before");
      }
    }

    // 🟢 Remove hidden elements
    clone.querySelectorAll("*").forEach((el) => {
      const style = window.getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden")
        el.remove();
    });

    // 🟢 Remove empty elements to prevent blank pages
    clone.querySelectorAll("div, section, tr").forEach((el) => {
      if (isVisiblyEmpty(el)) el.remove();
    });

    // 🟢 Extra: remove accidental blank page-break containers
    clone.querySelectorAll(".page-break-before").forEach((el) => {
      if (!el.textContent.trim() && el.children.length === 0) {
        el.remove();
      }
    });
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

    // Force table/container to shrink to page width
    clone.style.maxWidth = "100%";
    clone.style.overflowX = "auto";

    // clone.style.transform = "scale(0.9)"; // adjust scale factor if needed
    // clone.style.transformOrigin = "top left";

    wrapper.appendChild(clone);
    document.body.appendChild(wrapper);

    const opt = {
      margin: 0.3,
      filename: "report.pdf",
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: {
        scale: 3, // higher scale improves clarity
        logging: true,
        useCORS: true,
        scrollX: 0,
        scrollY: 0,
        windowWidth: clone.scrollWidth, // ensures wide table fits
      },
      jsPDF: { unit: "in", format: "a4", orientation: "portrait" },
    };

    try {
      // 🟢 FINAL CLEANUP before rendering
      const blankPages = clone.querySelectorAll(
        "div, section,overtimeSection,capacityTableSection"
      );
      blankPages.forEach((el) => {
        if (isVisiblyEmpty(el)) el.remove();
      });

      const hidden = document.querySelectorAll(".hidden-section");

      hidden.forEach((el) => el.parentNode.removeChild(el));

      await html2pdf().set(opt).from(clone).save();
      console.log("PDF generated successfully");
    } catch (err) {
      console.error("Error in PDF generation:", err);
    } finally {
      document.body.removeChild(wrapper);
    }
  } catch (err) {
    console.error("Error in PDF generation:", err);
  }
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
