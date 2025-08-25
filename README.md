# Jira Timesheet Utils  

A lightweight utility to simplify **time tracking and reporting in Jira**.  
It extends Jira’s native timesheet features with **bulk uploads, detailed reports, and overtime analytics**—helping teams and managers save time and gain clarity.  

---

## ✨ Features  

1. **Bulk Worklog Upload**  
   - Upload multiple worklogs at once from an XLSX file.  

2. **User-Specific Timesheets**  
   - Download timesheets for a single user or the whole team within any date range.  

3. **Detailed Reports**  
   - Generate sprint closure reports, project summaries, or custom period overviews.  

4. **User Filtering**  
   - Filter reports by specific team members for focused insights.  

5. **Overtime Analytics**  
   - Identify weekly or sprint-based overtime to track capacity and avoid burnout.  

---

## 📊 Why Use This Tool?  

- **Faster reporting** compared to Jira’s built-in tools.  
- **No plugins required** — self-hosted and lightweight.  
- **Excel-first approach** makes it easy to share and analyze data.  
- **Manager-friendly**: great for retrospectives, contractor billing, and team reviews.  

---

## 🚀 Getting Started  

### 1. Clone the repository  
```
git clone https://github.com/parmarravi/JiraToTimesheetConverter.git
cd JiraToTimesheetConverter
```
2. Install dependencies
```Copy
pip install -r requirements.txt
```
3. Configure settings
Update your Jira connection details in the configuration file (see example in repo).

4. Run the app
```
python app.py
```
5. Open in your browser:
```
http://localhost:5002
```


🖼️ Screenshots

| | |
|---|---|
| <img src="https://github.com/user-attachments/assets/a6ca8e0f-a876-4141-a3bc-e467c6b6b8d9" width="400"/> | <img src="https://github.com/user-attachments/assets/45521f65-f810-4c75-98bd-a450292005a8" width="400"/> |
| <img src="https://github.com/user-attachments/assets/0c26b88b-6608-497a-a239-f8989e2c9a7b" width="400"/> | <img src="https://github.com/user-attachments/assets/a4c618cf-95d9-43ba-920c-3aac4b168faa" width="400"/> |


📂 Example Workflows

1. Bulk Worklog Upload → Import worklogs from an Excel file instead of manual entry.

2. Weekly Team Report → Download a consolidated XLSX with team activity and capacity.

3. Overtime Monitoring → Track where overtime is spent across categories or projects.

🔍 Roadmap

 1. Export reports in CSV and PDF

 2. Schedule automatic report generation

 3. Integrations with Slack / Teams for notifications

 4. Enhanced error handling and logs

🤝 Contributing
Contributions are welcome!

Fork the repository

Create a feature branch

Submit a pull request

📜 License
MIT License


Visit: https://jiratotimesheetconverter.onrender.com/
