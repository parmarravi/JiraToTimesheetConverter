import socket
import pandas as pd
from io import BytesIO
from flask import Flask, render_template, request, send_file, redirect, url_for

app = Flask(__name__)

# --- Global variables to hold the application's state ---
global_df = None
global_authors = []
global_base_url = ""
original_filename = "timesheet.xlsx"


def get_local_ip():
    """Gets the local IP address of the machine to display a clickable link."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"
    finally:
        s.close()
    return local_ip

# --- Data Processing Functions ---

def process_timesheet(df, base_url):
    """Processes data for the detailed timesheet view."""
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df['Start Date'] = pd.to_datetime(df['Start Date']).dt.tz_localize(None)
    df['Date'] = pd.to_datetime(df['Start Date']).dt.strftime('%d/%b/%Y')
    df['Application/Project Name'] = df['Project Name']
    df['Activity/Task Done'] = df['Comment']
    df['Category'] = df['Labels']
    df['Ticket/Task #'] = df['Issue Key'].apply(lambda x: f"{base_url}{x}")
    df['Hours spent'] = df['Time Spent (seconds)'].apply(lambda x: round(x / 3600, 2))
    df['Start Time'] = df['Start Date'].dt.strftime('%I:%M %p')
    df['End Time'] = (df['Start Date'] + pd.to_timedelta(df['Time Spent (seconds)'], unit='s')).dt.strftime('%I:%M %p')
    df['Status'] = df['Issue Status']

    output_columns = [
        'Date', 'Application/Project Name', 'Activity/Task Done', 'Hours spent',
        'Category', 'Ticket/Task #', 'Start Time', 'End Time', 'Status'
    ]
    output_df = df[output_columns]
    category_totals = df.groupby('Category')['Hours spent'].sum().reset_index()
    return output_df, category_totals

def process_summary(df):
    """Generates a summary of time spent per task."""
    if df.empty:
        return pd.DataFrame()
    summary_df = df.groupby(
        ['Labels', 'Issue Summary', 'Author', 'Issue Status'],
        as_index=False
    )['Time Spent (seconds)'].sum()
    summary_df['Total Efforts (hrs)'] = round(summary_df['Time Spent (seconds)'] / 3600, 2)
    return summary_df[['Labels', 'Issue Summary', 'Author', 'Issue Status', 'Total Efforts (hrs)']]

def process_sprint_closure_report(df):
    """Generates the data for the Sprint Closure Report."""
    if df.empty:
        return BytesIO()
        
    df['Start Date'] = pd.to_datetime(df['Start Date'])
    df['Hours Spent'] = df['Time Spent (seconds)'] / 3600

   # Estimation
    df['Original Estimate'] = df['Original Estimate (seconds)'] / 3600
    df['Remaining Estimate'] = df['Remaining Estimate (seconds)'] / 3600


    # 1. Available Capacity
    weekdays_df = df[df['Start Date'].dt.weekday < 5].copy()
    working_days = weekdays_df.groupby('Author')['Start Date'].apply(lambda s: s.dt.date.nunique()).reset_index()
    working_days.columns = ['Team Member Name', 'Working Days']
    working_days['Available Capacity (Hours)'] = working_days['Working Days'] * 8

    # 2. Burned Capacity
    burned_capacity = pd.pivot_table(
        df, values='Hours Spent', index='Author', columns='Labels',
        aggfunc='sum', fill_value=0
    ).round(2)
    if not burned_capacity.empty:
        burned_capacity['Grand Total'] = burned_capacity.sum(axis=1)
    burned_capacity.reset_index(inplace=True)
    burned_capacity.rename(columns={'Author': 'Developer'}, inplace=True)

    # 3. Features and Tech Debt
    features_df = df[['Labels', 'Issue Summary', 'Original Estimate', 'Remaining Estimate', 'Issue Status', 'Author']].copy().drop_duplicates()
    features_df.rename(columns={'Labels': 'Category', 'Issue Status': 'Status', 'Author': 'Done By'}, inplace=True)
    features_df = features_df[['Category', 'Issue Summary', 'Original Estimate',  'Remaining Estimate', 'Status', 'Done By']]
    features_df.reset_index(drop=True, inplace=True)
    features_df.insert(0, 'Number', features_df.index + 1)

    # Write to an in-memory Excel file
    output_io = BytesIO()
    with pd.ExcelWriter(output_io, engine='xlsxwriter') as writer:
        workbook = writer.book
        worksheet = workbook.add_worksheet('Sprint Closure Report')
        header_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
        table_header_format = workbook.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1, 'text_wrap': True})
        worksheet.merge_range('A1:L1', 'Sprint Closure Report', header_format)
        
        if not working_days.empty:
            working_days.to_excel(writer, sheet_name='Sprint Closure Report', startrow=3, index=False)
        if not burned_capacity.empty:
            burned_capacity.to_excel(writer, sheet_name='Sprint Closure Report', startrow=3, startcol=4, index=False)
        if not features_df.empty:
            next_row = max(len(working_days), len(burned_capacity)) + 6
            features_df.to_excel(writer, sheet_name='Sprint Closure Report', startrow=next_row, index=False)
    output_io.seek(0)
    return output_io

# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the initial upload page."""
    return render_template('index.html', processed=False)

@app.route('/process', methods=['POST'])
def process_file_route():
    """
    Handles the file upload, cleans author names, stores data globally,
    and redirects to the report view.
    """
    global global_df, global_authors, global_base_url, original_filename
    if 'file' not in request.files or not request.form.get('base_url'):
        return "Missing file or base URL", 400

    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    original_filename = file.filename
    try:
        if original_filename.lower().endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        return f"Error reading file: {e}", 400
    
    # **FIX:** Clean whitespace from author names to ensure accurate filtering.
    if 'Author' in df.columns:
        df['Author'] = df['Author'].str.strip()

    # Store data globally
    global_df = df
    global_authors = sorted(df['Author'].unique().tolist())
    global_base_url = request.form['base_url']
    
    # Redirect to the report page
    return redirect(url_for('results'))

@app.route('/report')
def results():
    """
    Displays the report page. It filters the global data based on the
    'author' query parameter and generates the UI tables.
    """
    if global_df is None:
        return redirect(url_for('index'))

    selected_author = request.args.get('author', 'All')

    # Filter the main DataFrame based on selection
    if selected_author == 'All':
        display_df = global_df
    else:
        display_df = global_df[global_df['Author'] == selected_author].copy()

    # Generate data for the UI tables
    _, category_totals_df = process_timesheet(display_df.copy(), global_base_url)
    summary_df_for_ui = process_summary(display_df.copy())

    return render_template(
        'index.html',
        processed=True,
        authors=global_authors,
        selected_author=selected_author,
        category_totals=category_totals_df.to_dict(orient='records'),
        summary_data=summary_df_for_ui.to_dict(orient='records')
    )

@app.route('/download/<report_type>')
def download_report(report_type):
    """
    Generates and serves a specific report file on demand.
    The data is filtered based on the 'author' query parameter.
    """
    if global_df is None:
        return redirect(url_for('index'))

    selected_author = request.args.get('author', 'All')
    print(selected_author)

    # Filter the main DataFrame based on selection
    if selected_author == 'All':
        display_df = global_df
    else:
        display_df = global_df[global_df['Author'] == selected_author].copy()

    # Generate the requested file
    if report_type == 'detailed':
        output_df, _ = process_timesheet(display_df, global_base_url)
        file_io = BytesIO()
        output_df.to_excel(file_io, index=False, sheet_name='Detailed Timesheet')
        file_io.seek(0)
        download_name = original_filename.rsplit('.', 1)[0] + "_detailed.xlsx"
    elif report_type == 'summary':
        summary_df = process_summary(display_df)
        file_io = BytesIO()
        summary_df.to_excel(file_io, index=False, sheet_name='Summary Report')
        file_io.seek(0)
        download_name = "jira_summary.xlsx"
    elif report_type == 'sprint_closure':
        file_io = process_sprint_closure_report(display_df)
        download_name = "sprint_closure_report.xlsx"
    else:
        return "Invalid report type", 404

    return send_file(
        file_io,
        as_attachment=True,
        download_name=download_name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5002)
    
# if __name__ == '__main__':
#     local_ip = get_local_ip()
#     print(f" * Running on http://{local_ip}:5000")
#     app.run(host=local_ip, port=5000, debug=True)
