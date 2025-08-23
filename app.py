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

def process_timesheet(df, base_url, category_type="Activity", working_days=None):
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    if working_days is None:
        working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    # Map day names to weekday numbers (Monday=0, Sunday=6)
    day_name_to_num = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    working_day_nums = [day_name_to_num[day] for day in working_days if day in day_name_to_num]
    
    df['Start Date'] = pd.to_datetime(df['Start Date']).dt.tz_localize(None)
    df['Time'] = df['Start Date'].apply(lambda x: 'FullDay' if x.weekday() in working_day_nums else 'Holiday')
    
    # Create Hours column from Time Spent (seconds)
    df['Hours'] = df['Time Spent (seconds)'] / 3600
    
    # Group by date and sum hours
    daily_hours = df.groupby('Start Date')['Hours'].sum().reset_index()
    daily_hours['Hours'] = daily_hours['Hours'].round(2)
    
    # Get date range
    start_date = df['Start Date'].min()
    end_date = df['Start Date'].max()
    all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Create a complete date range DataFrame
    complete_dates = pd.DataFrame({'Start Date': all_dates})
    complete_dates['weekday'] = complete_dates['Start Date'].dt.weekday
    
    # Identify non-working days and working days
    non_working_days = all_dates[~all_dates.weekday.isin(working_day_nums)]
    working_days_dates = all_dates[all_dates.weekday.isin(working_day_nums)]
    
    # Get all dates from original data (including 0-hour entries) and actual work dates with hours > 0
    all_logged_dates = set(df['Start Date'].unique())
    actual_work_dates = set(daily_hours[daily_hours['Hours'] > 0]['Start Date'])
    
    # Detect leave days: working days with no logged entries between first and last logged dates
    if len(all_logged_dates) > 1:
        first_logged_date = min(all_logged_dates)
        last_logged_date = max(all_logged_dates)
        
        # Find working days between first and last logged date that have no entries at all
        potential_leave_dates = working_days_dates[
            (working_days_dates >= first_logged_date) & 
            (working_days_dates <= last_logged_date) &
            (~working_days_dates.isin(all_logged_dates))
        ]
    else:
        potential_leave_dates = pd.DatetimeIndex([])
    
    # Merge with actual data
    result = complete_dates.merge(daily_hours, on='Start Date', how='left')
    result['Hours'] = result['Hours'].fillna(0)
    
    # Add category and styling information with leave detection
    def categorize_day(row):
        date = row['Start Date']
        hours = row['Hours']
        
        if date in non_working_days:
            return 'Non-Working Day'
        elif date in potential_leave_dates:
            return 'Leave'
        elif hours > 0:
            return 'Work'
        else:
            return 'No Work'
    
    result['Category'] = result.apply(categorize_day, axis=1)
    
    result['Link'] = result.apply(lambda row: 
        f'<a href="{base_url}&date_filter={row["Start Date"].strftime("%Y-%m-%d")}" target="_blank">{row["Hours"]}</a>' 
        if row['Hours'] > 0 else str(row['Hours']), axis=1)
    
    # Format the date for display
    result['Date'] = result['Start Date'].dt.strftime('%d/%b/%Y')
    result['Time'] = result.apply(lambda row: 
        'FullDay' if row['Category'] == 'Work' else 
        ('Holiday' if row['Category'] == 'Non-Working Day' else 
         ('Leave' if row['Category'] == 'Leave' else 'No Work')), axis=1)
    
    # Create detailed timesheet from original data
    df['Date'] = df['Start Date'].dt.strftime('%d/%b/%Y')
    df['Ticket/Task #'] = df['Issue Key'].apply(lambda x: f"{base_url}{x}")
    df['Hours spent'] = df['Time Spent (seconds)'].apply(lambda x: round(x / 3600, 2))
    df['Start Time'] = df['Start Date'].dt.strftime('%I:%M %p')
    df['End Time'] = (df['Start Date'] + pd.to_timedelta(df['Time Spent (seconds)'], unit='s')).dt.strftime('%I:%M %p')
    df['Status'] = df['Issue Status']
    df['Application/Project Name'] = df['Project Name']
    df['Activity/Task Done'] = df['Comment']
    
    # Category driven by radio button selection with fallback
    if category_type == "Activity" and 'Activity' in df.columns:
        df['Category'] = df['Activity']
    elif category_type == "Label" and 'Labels' in df.columns:
        df['Category'] = df['Labels']
    elif category_type in df.columns:
        df['Category'] = df[category_type]  # Custom column selection
    elif 'Labels' in df.columns:
        df['Category'] = df['Labels']  # Fallback to Labels if available
    elif 'Activity' in df.columns:
        df['Category'] = df['Activity']  # Fallback to Activity if available
    else:
        df['Category'] = 'General'  # Default category if neither exists
    df['Remarks for any additional information'] = ""

    # Add non-working days to the detailed timesheet (only for dates without any work logged)
    non_working_days_without_work = non_working_days[~non_working_days.strftime('%d/%b/%Y').isin(df['Date'].unique())]
    non_working_df = pd.DataFrame({
        'Time': 'Holiday',
        'Date': non_working_days_without_work.strftime('%d/%b/%Y'),
        'Application/Project Name': '',
        'Activity/Task Done': '',
        'Hours spent': 0,
        'Category': 'Non-Working Day',
        'Ticket/Task #': '',
        'Start Time': '12:00 AM',
        'End Time': '',
        'Remarks for any additional information': '',
        'Status': ''
    })
    
    # Add leave days to the detailed timesheet (only for dates that have no work entries at all)
    # Filter out any potential leave dates that actually have work logged
    actual_leave_dates = potential_leave_dates[~potential_leave_dates.strftime('%d/%b/%Y').isin(df['Date'].unique())]
    leave_df = pd.DataFrame({
        'Time': 'Leave',
        'Date': actual_leave_dates.strftime('%d/%b/%Y'),
        'Application/Project Name': '',
        'Activity/Task Done': 'Leave Day',
        'Hours spent': 0,
        'Category': 'Leave',
        'Ticket/Task #': '',
        'Start Time': '12:00 AM',
        'End Time': '',
        'Remarks for any additional information': '',
        'Status': ''
    })

    output_df = pd.concat([df, non_working_df, leave_df], ignore_index=True)
    output_df['DateTime'] = pd.to_datetime(output_df['Date'] + ' ' + output_df['Start Time'],
                                           format='%d/%b/%Y %I:%M %p', errors='coerce')


    output_columns = [
        'Time', 'Date', 'Application/Project Name', 'Activity/Task Done', 'Hours spent',
        'Category', 'Ticket/Task #', 'Start Time', 'End Time', 'Remarks for any additional information', 'Status'
    ]

    output_df = output_df[output_columns + ['DateTime']]
    output_df = output_df.sort_values(by='DateTime', ascending=True).drop(columns=['DateTime'])

    # Handle empty/null categories
    df['Category'] = df['Category'].fillna('No Label/Empty')
    df.loc[df['Category'].str.strip() == '', 'Category'] = 'No Label/Empty'
    
    category_totals = df.groupby('Category')['Hours spent'].sum().reset_index()
    
    # Sort to put 'No Label/Empty' second to last, before total
    if 'No Label/Empty' in category_totals['Category'].values:
        no_label_row = category_totals[category_totals['Category'] == 'No Label/Empty']
        other_rows = category_totals[category_totals['Category'] != 'No Label/Empty']
        category_totals = pd.concat([other_rows, no_label_row], ignore_index=True)

    def highlight_non_working_days(val):
        """
        Highlight non-working days in yellow and leave days in light orange
        """
        if val == 'Non-Working Day':
            return 'background-color: yellow'
        elif val == 'Leave':
            return 'background-color: #ffcc99'  # Light orange for leave days
        return ''

    def highlight_holiday_rows(row):
        """
        Highlight entire row yellow when Time field is 'Holiday'
        """
        if row['Time'] == 'Holiday':
            return ['background-color: yellow'] * len(row)
        elif row['Time'] == 'Leave':
            return ['background-color: #ffcc99'] * len(row)
        else:
            return [''] * len(row)

    styled_df = output_df.style.apply(highlight_holiday_rows, axis=1)

    return styled_df, category_totals

def calculate_weekly_overtime(df, working_hours=8, working_days=None):
    """Calculate weekly overtime hours for chart visualization"""
    if df.empty:
        return {'weeks': [], 'overtime_hours': []}
    
    if working_days is None:
        working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    # Map day names to weekday numbers
    day_name_to_num = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    working_day_nums = [day_name_to_num[day] for day in working_days if day in day_name_to_num]
    
    df['Start Date'] = pd.to_datetime(df['Start Date']).dt.tz_localize(None)
    df['Hours spent'] = df['Time Spent (seconds)'] / 3600
    df['Weekday'] = df['Start Date'].dt.weekday
    df['Week'] = df['Start Date'].dt.isocalendar().week
    df['Year'] = df['Start Date'].dt.year
    df['Week_Year'] = df['Year'].astype(str) + '-W' + df['Week'].astype(str).str.zfill(2)
    
    # Calculate weekly overtime
    weekly_data = []
    for week_year in sorted(df['Week_Year'].unique()):
        week_df = df[df['Week_Year'] == week_year]
        
        # Get date range for this week
        week_dates = week_df['Start Date'].unique()
        if len(week_dates) > 0:
            start_date = min(week_dates).strftime('%d/%m/%Y')
            end_date = max(week_dates).strftime('%d/%m/%Y')
            date_range = f"{start_date} - {end_date}"
        else:
            date_range = ""
        
        # Non-working day overtime
        non_working_overtime = week_df[~week_df['Weekday'].isin(working_day_nums)]['Hours spent'].sum()
        
        # Daily overtime (hours > working_hours per day)
        daily_overtime = 0
        for date in week_df['Start Date'].unique():
            daily_hours = week_df[week_df['Start Date'] == date]['Hours spent'].sum()
            if pd.to_datetime(date).weekday() in working_day_nums and daily_hours > working_hours:
                daily_overtime += (daily_hours - working_hours)
        
        total_weekly_overtime = non_working_overtime + daily_overtime
        weekly_data.append({
            'week': week_year,
            'overtime_hours': round(total_weekly_overtime, 2),
            'date_range': date_range
        })
    
    return {
        'weeks': [item['week'] for item in weekly_data],
        'overtime_hours': [item['overtime_hours'] for item in weekly_data],
        'date_ranges': [item.get('date_range', '') for item in weekly_data]
    }

def calculate_overtime_hours(df, leave_days=0, holiday_days=0, working_hours=8, working_days=None):
    """Calculate overtime hours based on custom working days and daily overtime work."""
    if df.empty:
        return {'weekend_hours': 0, 'daily_overtime': 0, 'leave_overtime': 0, 'holiday_overtime': 0, 'total_overtime': 0}
    
    # Default working days (Monday to Friday)
    if working_days is None:
        working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    # Map day names to weekday numbers (Monday=0, Sunday=6)
    day_name_to_num = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    working_day_nums = [day_name_to_num[day] for day in working_days if day in day_name_to_num]
    
    df['Start Date'] = pd.to_datetime(df['Start Date']).dt.tz_localize(None)
    df['Hours spent'] = df['Time Spent (seconds)'] / 3600
    df['Weekday'] = df['Start Date'].dt.weekday
    
    # Non-working day overtime (all hours worked on non-working days)
    non_working_day_work = df[~df['Weekday'].isin(working_day_nums)]
    weekend_hours = non_working_day_work['Hours spent'].sum()
    
    # Daily overtime (hours > working_hours per day on working days)
    working_day_work = df[df['Weekday'].isin(working_day_nums)]
    daily_totals = working_day_work.groupby(working_day_work['Start Date'].dt.date)['Hours spent'].sum()
    daily_overtime = daily_totals[daily_totals > working_hours].apply(lambda x: x - working_hours).sum()
    
    # Leave and holiday overtime (convert days to hours using working_hours)
    leave_overtime = leave_days * working_hours
    holiday_overtime = holiday_days * working_hours
    
    total_overtime = weekend_hours + daily_overtime + leave_overtime + holiday_overtime
    
    return {
        'weekend_hours': round(weekend_hours, 2),
        'daily_overtime': round(daily_overtime, 2), 
        'leave_overtime': round(leave_overtime, 2),
        'holiday_overtime': round(holiday_overtime, 2),
        'total_overtime': round(total_overtime, 2)
    }

def process_summary(df, category_type="Activity", summary_type="Issue Summary"):
    """Generates a summary of time spent per task."""
    if df.empty:
        return pd.DataFrame()
    # ✅ Group by Activity or Labels based on category_type selection with fallback
    if category_type == "Activity" and 'Activity' in df.columns:
        group_col = 'Activity'
    elif category_type == "Label" and 'Labels' in df.columns:
        group_col = 'Labels'
    elif category_type in df.columns:
        group_col = category_type  # Custom column selection
    elif 'Labels' in df.columns:
        group_col = 'Labels'  # Fallback to Labels if available
    elif 'Activity' in df.columns:
        group_col = 'Activity'  # Fallback to Activity if available
    else:
        # If neither column exists, create a default category
        df['General'] = 'General'
        group_col = 'General'
    
    # ✅ Handle summary type selection (Issue Summary vs Parent Summary)
    if summary_type == "Parent Summary" and 'Parent Summary' in df.columns:
        summary_col = 'Parent Summary'
    elif 'Issue Summary' in df.columns:
        summary_col = 'Issue Summary'  # Default fallback
    else:
        summary_col = 'Issue Summary'  # Use as is even if column doesn't exist
    
    summary_df = df.groupby(
        [group_col, summary_col, 'Author', 'Issue Status'],
        as_index=False
    )['Time Spent (seconds)'].sum()
    summary_df['Total Efforts (hrs)'] = round(summary_df['Time Spent (seconds)'] / 3600, 2)
    summary_df.rename(columns={group_col: 'Category', summary_col: 'Summary'}, inplace=True)
    
    return summary_df[['Category', 'Summary', 'Author', 'Issue Status', 'Total Efforts (hrs)']]

def process_sprint_closure_report(df, summary_type="Issue Summary"):
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

    # 3. Features and Tech Debt - Handle summary type selection
    # ✅ Use selected summary type (Issue Summary vs Parent Summary)
    if summary_type == "Parent Summary" and 'Parent Summary' in df.columns:
        summary_col = 'Parent Summary'
    else:
        summary_col = 'Issue Summary'  # Default fallback
    
    # ✅ Group by Type of Work and Particular, then aggregate hours properly
    features_df = df.groupby(['Labels', summary_col, 'Author']).agg({
        'Original Estimate': 'sum',
        'Remaining Estimate': 'sum',
        'Issue Status': 'first'  # Take first status for grouped items
    }).reset_index()
    
    features_df.rename(columns={'Labels': 'Type of Work', summary_col: 'Particular', 'Original Estimate':'Extimated efforts','Remaining Estimate':'Actual Effrots', 'Issue Status': 'Remark', 'Author': 'Resource Name'}, inplace=True)
    features_df = features_df[['Type of Work', 'Particular', 'Resource Name', 'Extimated efforts',  'Actual Effrots', 'Remark']]
       # ✅ Sort by Author (Resource Name) and then by Type of Work
    features_df.sort_values(by=['Resource Name'], inplace=True)
    features_df.reset_index(drop=True, inplace=True)
    features_df.insert(0, 'Sr Number', features_df.index + 1)


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
    selected_category = request.args.get('category_type', 'Activity')  # default Activity
    selected_summary_type = request.args.get('summary_type', 'Issue Summary')  # default Issue Summary
    custom_column = request.args.get('custom_column', '')
    leave_days = float(request.args.get('leave_days', 0))
    holiday_days = float(request.args.get('holiday_days', 0))
    working_hours = float(request.args.get('working_hours', 8))
    working_days = request.args.getlist('working_days') or ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    # Handle custom column selection - check if it's a custom column name directly
    if selected_category not in ['Activity', 'Label'] and selected_category != 'Activity':
        # This means selected_category contains the custom column name
        custom_column = selected_category
    elif selected_category == 'Custom' and custom_column:
        selected_category = custom_column
    
    # Debug logging
    print(f"Debug - selected_category: {selected_category}, custom_column: {custom_column}, summary_type: {selected_summary_type}")

    # Filter the main DataFrame based on selection
    if selected_author == 'All':
        display_df = global_df
    else:
        display_df = global_df[global_df['Author'] == selected_author].copy()

    # Generate data for the UI tables with category type and summary type
    _, category_totals_df = process_timesheet(display_df.copy(), global_base_url, selected_category, working_days)
    summary_df_for_ui = process_summary(display_df.copy(), selected_category, selected_summary_type)
    
    # Calculate overtime hours
    overtime_data = calculate_overtime_hours(display_df.copy(), leave_days, holiday_days, working_hours, working_days)
    
    # Calculate weekly overtime data for chart
    weekly_overtime_data = calculate_weekly_overtime(display_df.copy(), working_hours, working_days)
    
    # Calculate category total sum
    category_total_sum = category_totals_df['Hours spent'].sum() if not category_totals_df.empty else 0

    return render_template(
        'index.html',
        processed=True,
        authors=global_authors,
        selected_author=selected_author,
        selected_category=selected_category,
        selected_summary_type=selected_summary_type,
        leave_days=leave_days,
        holiday_days=holiday_days,
        working_hours=working_hours,
        working_days=working_days,
        category_totals=category_totals_df.to_dict(orient='records'),
        category_total_sum=category_total_sum,
        summary_data=summary_df_for_ui.to_dict(orient='records'),
        overtime_data=overtime_data,
        weekly_overtime_data=weekly_overtime_data
    )

@app.route('/download_bulk/<report_type>')
def download_bulk_reports(report_type):
    """
    Downloads bulk reports for all authors when filter is 'All'
    Creates separate Excel sheets for each author
    """
    if global_df is None:
        return redirect(url_for('index'))
    
    selected_category = request.args.get('category_type', 'Activity')
    leave_days = float(request.args.get('leave_days', 0))
    holiday_days = float(request.args.get('holiday_days', 0))
    working_hours = float(request.args.get('working_hours', 8))
    working_days_param = request.args.get('working_days', '')
    if working_days_param:
        working_days = working_days_param.split(',')
    else:
        working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    # Get all unique authors
    all_authors = global_df['Author'].unique()
    
    # Create a BytesIO buffer for the Excel file
    file_io = BytesIO()
    
    with pd.ExcelWriter(file_io, engine='openpyxl') as writer:
        for author in all_authors:
            # Filter data for this author
            author_df = global_df[global_df['Author'] == author].copy()
            
            if report_type == 'detailed':
                output_df, _ = process_timesheet(author_df, global_base_url, selected_category, working_days)
                # Clean sheet name (Excel has restrictions)
                sheet_name = str(author)[:31].replace('/', '_').replace('\\', '_').replace('[', '').replace(']', '').replace('*', '').replace('?', '').replace(':', '')
                output_df.to_excel(writer, index=False, sheet_name=sheet_name)
    
    file_io.seek(0)
    download_name = f"bulk_timesheets_{len(all_authors)}_authors.xlsx"
    
    return send_file(
        file_io,
        as_attachment=True,
        download_name=download_name,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
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
    selected_category = request.args.get('category_type', 'Activity')  # default Activity
    selected_summary_type = request.args.get('summary_type', 'Issue Summary')  # default Issue Summary
    custom_column = request.args.get('custom_column', '')
    leave_days = float(request.args.get('leave_days', 0))
    holiday_days = float(request.args.get('holiday_days', 0))
    working_hours = float(request.args.get('working_hours', 8))
    # Handle working_days parameter - can be comma-separated string or list
    working_days_param = request.args.get('working_days', '')
    if working_days_param:
        working_days = working_days_param.split(',') if isinstance(working_days_param, str) else working_days_param
    else:
        working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    # Handle custom column selection - check if it's a custom column name directly
    if selected_category not in ['Activity', 'Label'] and selected_category != 'Activity':
        # This means selected_category contains the custom column name
        custom_column = selected_category
    elif selected_category == 'Custom' and custom_column:
        selected_category = custom_column
    
    # Debug logging
    print(f"Debug Download - selected_category: {selected_category}, custom_column: {custom_column}, summary_type: {selected_summary_type}")
    print(selected_author)

    # Filter the main DataFrame based on selection
    if selected_author == 'All':
        display_df = global_df
    else:
        display_df = global_df[global_df['Author'] == selected_author].copy()

    # Generate the requested file with category type
    if report_type == 'detailed':
        output_df, _ = process_timesheet(display_df, global_base_url, selected_category, working_days)
        file_io = BytesIO()
        output_df.to_excel(file_io, index=False, sheet_name='Detailed Timesheet')
        file_io.seek(0)
        download_name = original_filename.rsplit('.', 1)[0] + "_detailed.xlsx"
    elif report_type == 'summary':
        summary_df = process_summary(display_df, selected_category, selected_summary_type)
        file_io = BytesIO()
        summary_df.to_excel(file_io, index=False, sheet_name='Summary Report')
        file_io.seek(0)
        download_name = "jira_summary.xlsx"
    elif report_type == 'sprint_closure':
        file_io = process_sprint_closure_report(display_df, selected_summary_type)
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
