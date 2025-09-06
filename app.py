import socket
import pandas as pd
import json
from io import BytesIO
from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify, session
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='static')
app.secret_key = 'supersecretkey'  # Required for session to work

# Reset temp directory when server starts
from utils import reset_temp_directory
reset_temp_directory()

# @app.route('/reset', methods=['POST'])
# def reset():
#     """Reset the application state"""
#     session.clear()  # Clear all session data
#     reset_temp_directory()  # Reset temp directory
#     return redirect(url_for('index'))

@app.before_request
def cleanup_check():
    """Run cleanup periodically (every hour)"""
    from utils import should_run_cleanup, cleanup_old_files, mark_cleanup_complete
    
    if should_run_cleanup():
        cleanup_old_files()
        mark_cleanup_complete()

@app.route('/temp/<path:filename>')
def serve_temp_file(filename):
    """Serve files from temp directory"""
    from utils import get_temp_dir
    import os
    
    if not filename or '..' in filename:  # Basic security check
        return 'Invalid filename', 400
        
    temp_dir = get_temp_dir()
    return send_file(os.path.join(temp_dir, filename))

class DataNotFoundError(Exception):
    pass

def get_session_data():
    """Get data from session and temporary storage, raising DataNotFoundError if missing."""
    from utils import load_dataframe
    
    file_id = session.get('file_id')
    if not file_id:
        raise DataNotFoundError("No data in session")
    
    df = load_dataframe(file_id)
    if df is None:
        raise DataNotFoundError("Data file not found")
    
    base_url = session.get('user_base_url', '')
    holidays = session.get('holidays', [])
    authors = session.get('user_authors', [])
    
    return {
        'df': df,
        'base_url': base_url,
        'holidays': holidays,
        'authors': authors
    }

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

def process_timesheet(df, base_url, category_type="Activity", working_days=None, holidays=None):
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
    # Add: Identify holidays in the date range
    holiday_days = pd.to_datetime(list(holidays)) if holidays else pd.DatetimeIndex([])
    
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
    
    # Add category and styling information with leave detection and holiday
    def categorize_day(row):
        date = row['Start Date']
        hours = row['Hours']
        date_str = date.strftime('%Y-%m-%d')
        if date in non_working_days:
            return 'Non-Working Day'
        elif date in holiday_days:
            return 'Holiday'
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

# def calculate_weekly_overtime(df, working_hours=8, working_days=None, holidays=None):
#     """Calculate weekly overtime hours for chart visualization"""
#     if df.empty:
#         return {'weeks': [], 'overtime_hours': [], 'date_ranges': []}
    
#     if working_days is None:
#         working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
#     if holidays is None:
#         holidays = []

#     # Ensure proper datetime handling
#     df['Start Date'] = pd.to_datetime(df['Start Date'])
    
#     # Calculate hours from seconds and ensure proper date handling
#     df['Hours spent'] = df['Time Spent (seconds)'] / 3600
#     df['Week_Start'] = df['Start Date'].dt.to_period('W').apply(lambda r: r.start_time)
#     df['Week_End'] = df['Start Date'].dt.to_period('W').apply(lambda r: r.end_time)
#     df['Week_Number'] = df['Start Date'].dt.isocalendar().week
#     df['Year'] = df['Start Date'].dt.isocalendar().year
#     df['WeekKey'] = df['Year'].astype(str) + '-W' + df['Week_Number'].astype(str).str.zfill(2)
#     df['Weekday'] = df['Start Date'].dt.weekday
#     df['DateStr'] = df['Start Date'].dt.strftime('%Y-%m-%d')

#     # Map working days to numbers
#     day_name_to_num = {
#         'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
#         'Friday': 4, 'Saturday': 5, 'Sunday': 6
#     }
#     working_day_nums = [day_name_to_num[day] for day in working_days if day in day_name_to_num]

#     weekly_data = []
    
#     # Group by week and calculate overtime
#     for week_group in df.groupby(['WeekKey', 'Week_Start', 'Week_End']):
#         week_key = week_group[0][0]
#         week_start = week_group[0][1]
#         week_end = week_group[0][2]
#         week_df = week_group[1]
        
#         # Calculate each component of overtime
#         # 1. Non-working days overtime (only count actual work on weekends)
#         weekend_hours = week_df[~week_df['Weekday'].isin(working_day_nums)]['Hours spent'].sum()
        
#         # 2. Holiday overtime (only count actual work on holidays)
#         holiday_hours = week_df[week_df['DateStr'].isin(holidays)]['Hours spent'].sum()
        
#         # 3. Daily overtime on working days (only count hours beyond working_hours)
#         daily_overtime = 0
#         for date, day_df in week_df.groupby('Start Date'):
#             date_str = date.strftime('%Y-%m-%d')
#             # Only calculate overtime for working days that aren't holidays
#             if (pd.to_datetime(date).weekday() in working_day_nums and 
#                 date_str not in holidays):
#                 day_hours = day_df['Hours spent'].sum()
#                 if day_hours > working_hours:
#                     daily_overtime += (day_hours - working_hours)
        
#         # Sum all overtime components
#         total_overtime = weekend_hours + holiday_hours + daily_overtime
        
#         # Format date range
#         date_range = f"{week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}"
        
#         if total_overtime > 0:  # Only add weeks with overtime
#             weekly_data.append({
#                 'week': week_key,
#                 'overtime_hours': round(total_overtime, 2),
#                 'date_range': date_range
#             })

#     # Sort by week
#     weekly_data.sort(key=lambda x: x['week'])
    
#     # Print debug information
#     print("Weekly Overtime Data:")
#     for week in weekly_data:
#         print(f"Week: {week['week']}, Overtime: {week['overtime_hours']}")
        
#     return {
#         'weeks': [item['week'] for item in weekly_data],
#         'overtime_hours': [item['overtime_hours'] for item in weekly_data],
#         'date_ranges': [item['date_range'] for item in weekly_data]
#     }

def calculate_weekly_overtime(df, working_hours=8, working_days=None, holidays=None, author_filter="All"):
    """Calculate weekly overtime hours and total efforts for chart visualization"""

    if df.empty:
        return {'weeks': [], 'overtime_hours': [], 'total_hours': [], 'actual_hours': [], 'date_ranges': []}

    if working_days is None:
        working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    if holidays is None:
        holidays = []

    # Ensure datetime & hours
    df['Start Date'] = pd.to_datetime(df['Start Date']).dt.tz_localize(None)
    df['Hours spent'] = df['Time Spent (seconds)'] / 3600
    df['Week_Start'] = df['Start Date'].dt.to_period('W').apply(lambda r: r.start_time)
    df['Week_End'] = df['Start Date'].dt.to_period('W').apply(lambda r: r.end_time)
    df['Week_Number'] = df['Start Date'].dt.isocalendar().week
    df['Year'] = df['Start Date'].dt.isocalendar().year
    df['WeekKey'] = df['Year'].astype(str) + '-W' + df['Week_Number'].astype(str).str.zfill(2)

    # Author filter
    if author_filter != "All":
        df = df[df['Author'] == author_filter]

    weekly_data = []

    # Group week by week
    for (week_key, week_start, week_end), week_df in df.groupby(['WeekKey', 'Week_Start', 'Week_End']):
        # Calculate total hours for the week
        total_hours = week_df['Hours spent'].sum()
        
        # Calculate overtime hours
        overtime_summary = calculate_overtime_hours(
            week_df,
            leave_days=0,
            holiday_days=0,
            working_hours=working_hours,
            working_days=working_days,
            holidays=holidays
        )

        total_overtime = overtime_summary['total_overtime']
        actual_hours = total_hours - total_overtime

        # Include all weeks with any hours worked
        if total_hours > 0:
            date_range = f"{week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}"
            weekly_data.append({
                'week': week_key,
                'overtime_hours': round(total_overtime, 2),
                'total_hours': round(total_hours, 2),
                'actual_hours': round(max(0, actual_hours), 2),
                'date_range': date_range
            })

    # Sort by week
    weekly_data.sort(key=lambda x: x['week'])

    return {
        'weeks': [item['week'] for item in weekly_data],
        'overtime_hours': [item['overtime_hours'] for item in weekly_data],
        'total_hours': [item['total_hours'] for item in weekly_data],
        'actual_hours': [item['actual_hours'] for item in weekly_data],
        'date_ranges': [item['date_range'] for item in weekly_data]
    }


def calculate_weekly_overtime_for_author(df, working_hours=8, working_days=None, holidays=None):
    """
    A helper function to calculate overtime for a given weekly dataframe.
    Returns overtime per author for EMA calculation.
    """
    if df.empty:
        return {}
    
    if working_days is None:
        working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    if holidays is None:
        holidays = []
    
    overtime_per_author = {}
    for author in df['Author'].unique():
        author_df = df[df['Author'] == author]
        
        # Calculate detailed overtime using existing function
        overtime_data = calculate_overtime_hours(
            author_df, 0, 0, working_hours, working_days, holidays
        )
        
        total_overtime = overtime_data['total_overtime']
        overtime_per_author[author] = max(0, total_overtime)  # Ensure overtime is not negative
        
    return overtime_per_author


def update_burnout_risk_scores(current_df, historical_scores=None, smoothing_factor=0.4, working_hours=8, working_days=None, holidays=None):
    """
    Updates the burnout risk scores based on the current data and historical scores using EMA.
    Returns the updated scores and a list of current burnout cases.
    """
    if current_df.empty:
        return {}, []
    
    if historical_scores is None:
        historical_scores = {}
    
    # 1. Calculate overtime for the current period
    current_overtime = calculate_weekly_overtime_for_author(current_df, working_hours, working_days, holidays)
    
    updated_scores = historical_scores.copy()
    all_authors = set(list(historical_scores.keys()) + list(current_overtime.keys()))

    burnout_cases = []

    for author in all_authors:
        # 2. Get previous score and current overtime
        previous_score = historical_scores.get(author, 0)
        current_overtime_hours = current_overtime.get(author, 0)  # 0 overtime if they didn't log time

        # 3. Apply the EMA formula to calculate the new score
        new_score = (current_overtime_hours * smoothing_factor) + (previous_score * (1 - smoothing_factor))
        updated_scores[author] = new_score

        # 4. Determine burnout level based on the NEW score and thresholds
        burnout_level = "Low"
        message = ""
        
        if new_score >= 12:  # Critical threshold
            burnout_level = "Critical"
            message = f"🔴 CRITICAL: {author}'s workload strain score is {new_score:.1f}, indicating sustained high overtime."
        elif new_score >= 8:  # High risk threshold
            burnout_level = "High"
            message = f"🟠 HIGH RISK: {author}'s workload strain score is {new_score:.1f}. Monitor closely."
        elif new_score >= 5:  # Moderate threshold
            burnout_level = "Moderate"
            message = f"🟡 MODERATE: {author}'s workload strain score is {new_score:.1f}. Recent overtime is increasing risk."
        
        if burnout_level != "Low":
            # Get detailed overtime breakdown for display
            author_df = current_df[current_df['Author'] == author]
            if not author_df.empty:
                overtime_data = calculate_overtime_hours(
                    author_df, 0, 0, working_hours, working_days, holidays
                )
                total_hours = (author_df['Time Spent (seconds)'] / 3600).sum()
                overtime_percentage = (current_overtime_hours / total_hours * 100) if total_hours > 0 else 0
            else:
                overtime_data = {'weekend_hours': 0, 'daily_overtime': 0, 'holiday_overtime': 0}
                total_hours = 0
                overtime_percentage = 0
            
            burnout_cases.append({
                'author': author,
                'workload_strain_score': new_score,
                'current_overtime': current_overtime_hours,
                'total_overtime': current_overtime_hours,  # For template compatibility
                'total_hours': total_hours,
                'overtime_percentage': overtime_percentage,
                'burnout_level': burnout_level,
                'message': message,
                'weekend_hours': overtime_data['weekend_hours'],
                'daily_overtime': overtime_data['daily_overtime'],
                'holiday_overtime': overtime_data['holiday_overtime']
            })

    # Sort by the new strain score
    burnout_cases.sort(key=lambda x: x['workload_strain_score'], reverse=True)
    
    return updated_scores, burnout_cases


def detect_burnout(df, working_hours=8, working_days=None, holidays=None, burnout_threshold=10):
    """
    Detect team members who are experiencing burnout using EMA Workload Strain Score.
    Returns a list of burnout cases with details.
    """
    if df.empty:
        return []
    
    # For now, we'll use a simple historical scores simulation
    # In a real application, this would be stored in a database
    # and retrieved/updated with each analysis
    
    # Simulate some historical scores (in production, load from storage)
    historical_scores = {}
    for author in df['Author'].unique():
        # Initialize with a baseline score based on current data patterns
        author_df = df[df['Author'] == author]
        if not author_df.empty:
            current_overtime_data = calculate_overtime_hours(
                author_df, 0, 0, working_hours, working_days, holidays
            )
            # Start with 70% of current overtime as historical baseline
            historical_scores[author] = current_overtime_data['total_overtime'] * 0.7
    
    # Use EMA-based burnout detection
    updated_scores, burnout_cases = update_burnout_risk_scores(
        df, historical_scores, smoothing_factor=0.4, 
        working_hours=working_hours, working_days=working_days, holidays=holidays
    )
    
    # In production, save updated_scores back to storage here
    
    return burnout_cases

def calculate_overtime_hours(df, leave_days=0, holiday_days=0, working_hours=8, working_days=None, holidays=None):
    """
    Calculate overtime hours based on custom working days and daily overtime work.
    For 'All' authors, sum up all overtime components across all authors.
    """
    if df.empty:
        return {'weekend_hours': 0, 'daily_overtime': 0, 'leave_overtime': 0, 'holiday_overtime': 0, 'total_overtime': 0}
    
    if working_days is None:
        working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    if holidays is None:
        holidays = []

    day_name_to_num = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    working_day_nums = [day_name_to_num[day] for day in working_days if day in day_name_to_num]

    df['Start Date'] = pd.to_datetime(df['Start Date']).dt.tz_localize(None)
    df['Hours spent'] = df['Time Spent (seconds)'] / 3600
    df['Weekday'] = df['Start Date'].dt.weekday
    df['DateStr'] = df['Start Date'].dt.strftime('%Y-%m-%d')

    # Group by Author and Date for daily overtime calculation
    daily_work = df.groupby(['Author', 'Start Date', 'Weekday', 'DateStr'])['Hours spent'].sum().reset_index()

    # Calculate overtime components for each author
    overtime_by_author = []
    for author in df['Author'].unique():
        author_data = daily_work[daily_work['Author'] == author]
        weekend_hours = author_data[~author_data['Weekday'].isin(working_day_nums)]['Hours spent'].sum()
        holiday_hours = author_data[author_data['DateStr'].isin(holidays)]['Hours spent'].sum()
        working_day_records = author_data[
            (author_data['Weekday'].isin(working_day_nums)) & 
            (~author_data['DateStr'].isin(holidays))
        ]
        daily_overtime = working_day_records[working_day_records['Hours spent'] > working_hours]['Hours spent'].apply(lambda x: x - working_hours).sum()
        leave_overtime = leave_days * working_hours
        total_overtime = weekend_hours + holiday_hours + daily_overtime + leave_overtime

        overtime_by_author.append({
            'author': author,
            'weekend_hours': round(weekend_hours, 2),
            'holiday_overtime': round(holiday_hours, 2),
            'daily_overtime': round(daily_overtime, 2),
            'leave_overtime': round(leave_overtime, 2),
            'total_overtime': round(total_overtime, 2)
        })

    # If only one author selected, return their overtime
    if len(overtime_by_author) == 1:
        return overtime_by_author[0]

    # For 'All' authors, sum up the components
    total_overtime = {
        'weekend_hours': round(sum(a['weekend_hours'] for a in overtime_by_author), 2),
        'holiday_overtime': round(sum(a['holiday_overtime'] for a in overtime_by_author), 2),
        'daily_overtime': round(sum(a['daily_overtime'] for a in overtime_by_author), 2),
        'leave_overtime': round(sum(a['leave_overtime'] for a in overtime_by_author), 2)
    }
    total_overtime['total_overtime'] = round(sum(total_overtime.values()), 2)
    return total_overtime

def process_summary(df, category_type="Activity", summary_type="Issue Summary", sort_by="Author", is_reverse_timesheet=False):
    """Generates a summary of time spent per task."""
    if df.empty:
        return pd.DataFrame()
    
    if is_reverse_timesheet:
        # For reverse timesheet, ALWAYS group by Issue Key regardless of sort option
        summary_df = df.groupby(['Issue Key'], as_index=False).agg({
            'Time Spent (seconds)': 'sum',
            'Author': 'first',  # Take first author for the ticket
            'Issue Status': 'first',  # Take first status
            'Issue Summary': 'first'  # Take first summary
        })
        summary_df['Total Efforts (hrs)'] = round(summary_df['Time Spent (seconds)'] / 3600, 2)
        
        # Use Activity if available, otherwise use 'General'
        if 'Activity' in df.columns:
            summary_df['Category'] = df.groupby(['Issue Key'])['Activity'].first().values
        else:
            summary_df['Category'] = 'General'
        
        summary_df['Summary'] = summary_df['Issue Summary']
        
        # Apply sorting based on sort_by parameter
        if sort_by == "Total Efforts":
            summary_df = summary_df.sort_values(['Total Efforts (hrs)', 'Issue Key'], ascending=[False, True])
        elif sort_by == "Author":
            summary_df = summary_df.sort_values(['Author', 'Issue Key'], ascending=[True, True])
        else:  # Default or "Ticket/Task #"
            summary_df = summary_df.sort_values(['Issue Key'], ascending=[True])
        
        return summary_df[['Category', 'Summary', 'Author', 'Issue Status', 'Issue Key', 'Total Efforts (hrs)']]
    
    # Original logic for regular Jira exports
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
    
    # Group by and include Issue Key for sorting purposes
    summary_df = df.groupby(
        [group_col, summary_col, 'Author', 'Issue Status'],
        as_index=False
    )['Time Spent (seconds)'].sum()
    summary_df['Total Efforts (hrs)'] = round(summary_df['Time Spent (seconds)'] / 3600, 2)
    summary_df.rename(columns={group_col: 'Category', summary_col: 'Summary'}, inplace=True)
    
    # Sort the summary data based on the sort_by parameter
    if sort_by == "Total Efforts":
        # Sort by Total Efforts (hrs) in descending order, then by Author
        summary_df = summary_df.sort_values(['Total Efforts (hrs)', 'Author'], ascending=[False, True])
    elif sort_by == "Ticket/Task #":
        # Sort by Issue Key (Ticket/Task #)
        summary_df = summary_df.sort_values(['Issue Key', 'Author'], ascending=[True, True])
    else:
        # Default sort by Author (ascending), then by Total Efforts (hrs) descending
        summary_df = summary_df.sort_values(['Author', 'Total Efforts (hrs)'], ascending=[True, False])
    
    return summary_df[['Category', 'Summary', 'Author', 'Issue Status', 'Total Efforts (hrs)']]

def process_reverse_timesheet(df):
    """
    Process uploaded timesheet template and convert it back to Jira-like format for dashboard visualization.
    Expects timesheet with columns: Time, Date, Application/Project Name, Activity/Task Done, Hours spent, Category, etc.
    """
    if df.empty:
        return pd.DataFrame()
    
    # Map timesheet columns back to Jira format
    reverse_df = pd.DataFrame()
    
    # Required mappings for dashboard visualization
    # Handle Author column with proper fallback for missing or empty values
    if 'Author' in df.columns:
        reverse_df['Author'] = df['Author'].fillna('Unknown').replace('', 'Unknown').astype(str)
        # Replace any remaining empty strings or whitespace-only strings
        reverse_df['Author'] = reverse_df['Author'].apply(lambda x: 'Unknown' if not x or x.strip() == '' else x.strip())
    else:
        reverse_df['Author'] = 'Unknown'
    
    reverse_df['Start Date'] = pd.to_datetime(df['Date'], format='%d/%b/%Y', errors='coerce')
    reverse_df['Time Spent (seconds)'] = df['Hours spent'] * 3600  # Convert hours back to seconds
    reverse_df['Project Name'] = df.get('Application/Project Name', 'Unknown Project')
    reverse_df['Comment'] = df.get('Activity/Task Done', '')
    reverse_df['Issue Status'] = df.get('Status', 'Unknown')
    
    # Handle Category mapping (Labels or Activity)
    if 'Category' in df.columns:
        reverse_df['Labels'] = df['Category']
        reverse_df['Activity'] = df['Category']
    
    # Generate synthetic Issue Key and Summary if not present
    reverse_df['Issue Key'] = df.get('Ticket/Task #', '').apply(lambda x: x.split('/')[-1] if '/' in str(x) else f"TASK-{hash(str(x)) % 10000}")
    reverse_df['Issue Summary'] = df.get('Activity/Task Done', 'Imported Task')
    reverse_df['Parent Summary'] = reverse_df['Issue Summary']  # Use same for parent
    
    # Add estimation fields (set to 0 if not available)
    reverse_df['Original Estimate (seconds)'] = 0
    reverse_df['Remaining Estimate (seconds)'] = 0
    
    # Filter out holiday/leave entries for cleaner dashboard
    reverse_df = reverse_df[~reverse_df['Comment'].isin(['Leave Day', '', 'Holiday'])]
    reverse_df = reverse_df[reverse_df['Time Spent (seconds)'] > 0]
    
    # Clean up any NaN values
    reverse_df = reverse_df.fillna('')
    
    return reverse_df

# Convert to datetime and reformat
def format_date(date_str):
    if date_str:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    return ""

def process_sprint_closure_report(df, summary_type="Issue Summary"):
    """
    Generates the data for the Sprint Closure Report.
    Fixed to properly calculate user-based efforts mapping.
    """
    if df.empty:
        return BytesIO()
        
    df['Start Date'] = pd.to_datetime(df['Start Date'])
    df['Hours Spent'] = df['Time Spent (seconds)'] / 3600

    # Convert estimation fields to hours
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
    if summary_type == "Parent Summary" and 'Parent Summary' in df.columns:
        summary_col = 'Parent Summary'
    else:
        summary_col = 'Issue Summary'  # Default fallback
    
    # ✅ FIXED: Calculate user-based efforts mapping
    # Group by Labels, Summary, and Author to get per-user task breakdown
    user_task_summary = df.groupby(['Labels', summary_col, 'Author']).agg({
        'Original Estimate': 'first',  # Take the original estimate for the task
        'Hours Spent': 'sum',  # Sum actual hours spent by this user on this task
        'Issue Status': 'first'  # Take first status for grouped items
    }).reset_index()
    
    # Now calculate estimated and actual efforts based on user participation
    features_list = []
    
    # Group by Labels and Summary to get all tasks
    for (label, summary), task_group in user_task_summary.groupby(['Labels', summary_col]):
        # Get all users who worked on this task
        users_on_task = task_group['Author'].tolist()
        total_users = len(users_on_task)
        
        # Get the original estimate for this task (should be same for all users)
        original_estimate = task_group['Original Estimate'].iloc[0]
        
        # For each user who worked on this task
        for _, user_row in task_group.iterrows():
            user = user_row['Author']
            actual_hours = user_row['Hours Spent']
            status = user_row['Issue Status']
            
            # Calculate estimated effort for this user:
            # If multiple users worked on the task, split the estimate proportionally
            # based on their actual contribution
            total_actual_hours = task_group['Hours Spent'].sum()
            if total_actual_hours > 0:
                # Proportional allocation based on actual work done
                user_estimated_effort = original_estimate * (actual_hours / total_actual_hours)
            else:
                # If no actual work logged, split estimate equally among users
                user_estimated_effort = original_estimate / total_users if total_users > 0 else original_estimate
            
            features_list.append({
                'Type of Work': label,
                'Particular': summary,
                'Resource Name': user,
                'Extimated efforts': round(user_estimated_effort, 2),
                'Actual Effrots': round(actual_hours, 2),
                'Remark': status
            })
    
    # Convert to DataFrame
    features_df = pd.DataFrame(features_list)
    
    # Sort by Resource Name (Author) and then by Type of Work
    if not features_df.empty:
        features_df.sort_values(by=['Resource Name', 'Type of Work'], inplace=True)
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


def availableCapacity(df, selectedAuthor=None, workingHours=8, workingDays=None, holidays=None, customColumn=None):
    """
    Calculate available capacity and category-wise hours per team member.
    Mirrors the logic from process_sprint_closure_report.
    Returns: (capacity_list, category_hours_list)
    """

    if df.empty:
        return [], []

    # Ensure Start Date is datetime
    df['Start Date'] = pd.to_datetime(df['Start Date'])
    df['Hours Spent'] = df['Time Spent (seconds)'] / 3600

    # --- Capacity Calculation ---
    weekdays_df = df[df['Start Date'].dt.weekday < 5].copy()

    working_days = (
        weekdays_df.groupby('Author')['Start Date']
        .apply(lambda s: s.dt.date.nunique())
        .reset_index()
    )
    working_days.columns = ['Team Member Name', 'Working Days']
    working_days['Available Capacity (Hours)'] = working_days['Working Days'] * workingHours

    if 'LeaveDays' in df.columns:
        leave_info = df.groupby('Author')['LeaveDays'].max().reset_index()
        leave_info.columns = ['Team Member Name', 'Leave Days']
        working_days = working_days.merge(leave_info, on='Team Member Name', how='left')
        working_days['Leave Days'] = working_days['Leave Days'].fillna(0).astype(int)
        working_days['Adjusted Working Days'] = working_days['Working Days'] - working_days['Leave Days']
        working_days['Adjusted Capacity (Hours)'] = working_days['Adjusted Working Days'] * workingHours

    capacity_list = working_days.to_dict(orient='records')

    columnNameFilter =customColumn if customColumn in df.columns else 'Labels'
    print("customColumn:", customColumn)
    print(columnNameFilter)
    # --- Category-wise Hours (Burned Capacity) ---
    burned_capacity = pd.pivot_table(
        df, values='Hours Spent', index='Author', columns=columnNameFilter,
        aggfunc='sum', fill_value=0
    ).round(2)

    if not burned_capacity.empty:
        burned_capacity['Grand Total'] = burned_capacity.sum(axis=1)
    burned_capacity.reset_index(inplace=True)
    burned_capacity.rename(columns={'Author': 'Team Member Name'}, inplace=True)

    category_hours_list = burned_capacity.to_dict(orient='records')

    return capacity_list, category_hours_list

def getStoryAndTaskCount(df):
    """
    Returns the count of unique stories and tasks in the global dataframe.
    """
   
   # --- Calculate unique counts ---
    task_count = 0
    story_count = 0
    unique_story_ids = []
    unique_task_ids = []

    if not df.empty:
                    # --- Handle task keys ---
        task_keys = []
        if 'Issue Key' in df.columns:
            task_keys = df['Issue Key'].dropna().tolist()
        for key in task_keys:
            if key not in unique_task_ids:
                unique_task_ids.append(key)

        # --- Handle parent keys ---
        parent_keys = []
        if 'Parent Key' in df.columns:
            parent_keys = df['Parent Key'].dropna().tolist()
        for key in parent_keys:
            if key not in unique_story_ids:
                unique_story_ids.append(key)

        story_count = len(unique_story_ids)
        task_count = len(unique_task_ids)


    return story_count, task_count


def getAuthorSubtaskCount(df):
    """
    Returns a list of (Author, Subtask Count) for each author.
    Only counts issues where Issue Type = 'Sub-task'.
    """
    author_task_list = []

    print(f"Debug - getAuthorSubtaskCount: DataFrame shape: {df.shape}")
    if 'Author' in df.columns:
        print(f"Debug - getAuthorSubtaskCount: Unique authors: {df['Author'].unique().tolist()}")
    if 'Issue Type' in df.columns:
        print(f"Debug - getAuthorSubtaskCount: Unique Issue Types: {df['Issue Type'].unique().tolist()}")

    if not df.empty and {'Author', 'Issue Key', 'Issue Type'}.issubset(df.columns):
        # Filter only subtasks - check for different possible values
        subtask_df = df[df['Issue Type'].str.contains('sub', case=False, na=False)]
        print(f"Debug - getAuthorSubtaskCount: Subtask DataFrame shape: {subtask_df.shape}")

        # Group by author and count unique subtasks Worklog Id
        for author, group in subtask_df.groupby('Author'):
            unique_tasks = group['Issue Key'].dropna().unique()
            author_task_list.append({
                "Author": author,
                "count": len(unique_tasks)
            })

    print("author_task_list",author_task_list) 
    return author_task_list
# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the initial upload page."""
    from utils import remove_dataframe
    
    # Clean up temporary data
    file_id = session.get('file_id')
    if file_id:
        remove_dataframe(file_id)  # This now also cleans up logo files
    
    # Clear all relevant session data
    keys_to_clear = ['file_id', 'logo_filename', 'project_name', 'start_date', 'end_date', 
                     'key_insights', 'user_base_url', 'holidays', 'user_authors']
    for key in keys_to_clear:
        session.pop(key, None)
    session.clear()
    return render_template('index.html', processed=False)

@app.route('/api/session-check')
def session_check():
    """Check if all required session data is present"""
    try:
        data = get_session_data()
        return jsonify({
            "status": "valid",
            "data": {
                "holidays": session.get('holidays', []),
                "weekly_overtime_data": None,
                "category_totals": None,
                "overtime_data": {
                    'weekend_hours': 0,
                    'daily_overtime': 0,
                    'leave_overtime': 0,
                    'holiday_overtime': 0,
                    'total_overtime': 0
                }
            }
        })
    except DataNotFoundError:
        return jsonify({"status": "invalid"}), 404

@app.route('/process', methods=['POST'])
def process_file_route():
    """
    Handles the file upload, cleans author names, stores data in temporary storage,
    and redirects to the report view.
    """
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
    
    # Clean whitespace from author names to ensure accurate filtering.
    if 'Author' in df.columns:
        df['Author'] = df['Author'].str.strip()

    # Debug: Check for duplicate authors
    print(f"Debug - Raw authors from CSV: {df['Author'].unique().tolist()}")
    unique_authors = sorted(df['Author'].unique().tolist())
    print(f"Debug - Unique authors after sorting: {unique_authors}")
    print(f"Debug - Author count: {len(unique_authors)}")

    # Store DataFrame in temporary file
    from utils import save_dataframe
    file_id = save_dataframe(df)
    
    # Store only metadata in session
    session['file_id'] = file_id
    session['user_authors'] = unique_authors
    session['user_base_url'] = request.form['base_url']
    session['fileName'] = original_filename
    
    # Redirect to the report page
    return redirect(url_for('results'))

@app.route('/process_reverse', methods=['POST'])
def process_reverse_timesheet_route():
    """
    Handles reverse timesheet upload - converts timesheet template back to dashboard data.
    """



    if 'file' not in request.files:
        return "Missing timesheet file", 400

    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    original_filename = file.filename
    try:
        if original_filename.lower().endswith('.csv'):
            timesheet_df = pd.read_csv(file)
        else:
            timesheet_df = pd.read_excel(file)
    except Exception as e:
        return f"Error reading timesheet file: {e}", 400
    
    # Validate timesheet format
    required_columns = ['Date', 'Hours spent']
    missing_columns = [col for col in required_columns if col not in timesheet_df.columns]
    if missing_columns:
        return f"Invalid timesheet format. Missing columns: {', '.join(missing_columns)}", 400
    
    # Process reverse timesheet
    try:
        df = process_reverse_timesheet(timesheet_df)
        if df.empty:
            return "No valid data found in timesheet", 400
    except Exception as e:
        return f"Error processing timesheet: {e}", 400
    
    # Clean whitespace from author names and ensure no empty values
    if 'Author' in df.columns:
        df['Author'] = df['Author'].astype(str).str.strip()
        # Replace any empty strings with 'Unknown'
        df['Author'] = df['Author'].replace('', 'Unknown').replace('nan', 'Unknown')
        # Handle any remaining NaN values
        df['Author'] = df['Author'].fillna('Unknown')

    # Get unique authors list - ensure 'Unknown' is included if present
    unique_authors = sorted(df['Author'].unique().tolist()) if 'Author' in df.columns else ['Unknown']
    
    # Ensure we have at least one author
    if not unique_authors or len(unique_authors) == 0:
        unique_authors = ['Unknown']

    # Store DataFrame in temporary file (same as regular Jira upload)
    from utils import save_dataframe
    file_id = save_dataframe(df)
    
    # Store only metadata in session (same pattern as process_file_route)
    session['file_id'] = file_id
    session['user_authors'] = unique_authors
    session['user_base_url'] = "https://imported-timesheet/"
    session['fileName'] = original_filename
    
    # Redirect to the report page
    return redirect(url_for('results'))

@app.route('/upload_holidays', methods=['POST'])
def upload_holidays():
    """
    Accepts an Excel file with a single column of dates and updates the holidays in the session.
    """
    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    try:
        df = pd.read_excel(file)
        if df.empty:
            return jsonify({'success': False, 'error': 'Excel file is empty'}), 400
            
        # Try to identify date column
        date_columns = []
        for col in df.columns:
            # Try parsing as date with various formats
            try:
                dates = pd.to_datetime(df[col], errors='coerce')
                if not dates.isna().all():  # If at least some values parsed as dates
                    date_columns.append(col)
            except:
                continue
        
        if not date_columns:
            return jsonify({'success': False, 'error': 'No valid date columns found'}), 400
            
        # Use first date column found
        dates = pd.to_datetime(df[date_columns[0]], errors='coerce')
        valid_dates = dates.dropna()
        
        if len(valid_dates) == 0:
            return jsonify({'success': False, 'error': 'No valid dates found'}), 400
            
        # Update holidays in session
        current_holidays = set(session.get('holidays', []))
        current_holidays.update(valid_dates.dt.strftime('%Y-%m-%d').tolist())
        session['holidays'] = list(current_holidays)
        
        return jsonify({
            'success': True, 
            'holidays': session['holidays'],
            'message': f'Imported {len(valid_dates)} dates successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/get_holidays', methods=['GET'])
def get_holidays():
    """Returns the current list of holidays from the session."""
    return jsonify({'holidays': session.get('holidays', [])})

def calculate_overtime_list(df, leave_days=0, working_hours=8, working_days=None, holidays=None):
    """Return list of authors with non-zero overtime."""
    if df.empty:
        return []

    if working_days is None:
        working_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    if holidays is None:
        holidays = []

    # Reuse same logic from calculate_overtime_hours
    overtime = calculate_overtime_hours(df, leave_days, 0, working_hours, working_days, holidays)

    # If calculate_overtime_hours returned aggregate (dict, not list), rebuild per author
    df['Start Date'] = pd.to_datetime(df['Start Date']).dt.tz_localize(None)
    df['Hours spent'] = df['Time Spent (seconds)'] / 3600
    df['Weekday'] = df['Start Date'].dt.weekday
    df['DateStr'] = df['Start Date'].dt.strftime('%Y-%m-%d')

    day_name_to_num = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    working_day_nums = [day_name_to_num[day] for day in working_days]

    daily_work = df.groupby(['Author', 'Start Date', 'Weekday', 'DateStr'])['Hours spent'].sum().reset_index()
    overtime_list = []

    for author in df['Author'].unique():
        author_data = daily_work[daily_work['Author'] == author]
        weekend_hours = author_data[~author_data['Weekday'].isin(working_day_nums)]['Hours spent'].sum()
        holiday_hours = author_data[author_data['DateStr'].isin(holidays)]['Hours spent'].sum()
        working_day_records = author_data[(author_data['Weekday'].isin(working_day_nums)) & (~author_data['DateStr'].isin(holidays))]
        daily_overtime = working_day_records[working_day_records['Hours spent'] > working_hours]['Hours spent'].apply(lambda x: x - working_hours).sum()
        leave_overtime = leave_days * working_hours
        total_overtime = weekend_hours + holiday_hours + daily_overtime + leave_overtime

        if total_overtime > 0:  # Only include authors with overtime
            overtime_list.append({
                "Author": author,
                "Total Overtime (hrs)": round(total_overtime, 2)
            })

    return overtime_list
          
                
@app.route('/set_holidays', methods=['POST'])
def set_holidays():
    """
    Accepts a JSON list of dates (YYYY-MM-DD) from the calendar UI and updates holidays in the session.
    """
    try:
        data = request.get_json()
        holidays = data.get('holidays', [])
        session['holidays'] = list(set(holidays))
        return jsonify({'success': True, 'holidays': session['holidays']})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400




@app.route('/report_toolbar', methods=['Post'])
def reportToolbar():
    """
    Handles project name and logo upload from toolbar.
    Stores them in session so they persist across /report GET requests.
    """
    project_name = request.form.get('project_name')
    if project_name:
        session['project_name'] = project_name

    logo_file = request.files.get('project_logo')

    if logo_file and logo_file.filename != '':
        from werkzeug.utils import secure_filename
        import os
        import uuid
        from utils import get_temp_dir

        # Get file extension and session ID
        _, ext = os.path.splitext(logo_file.filename)
        file_id = session.get('file_id')
        
        if not file_id:
            file_id = str(uuid.uuid4())
            session['file_id'] = file_id
            
        # Create filename using session's file_id
        temp_filename = f"logo_{file_id}{ext}"
        # Save in temp directory
        temp_dir = get_temp_dir()
        logo_path = os.path.join(temp_dir, temp_filename)
        logo_file.save(logo_path)
        session['logo_filename'] = temp_filename  # Store temp filename in session

    # Date range
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    if start_date:
        session['start_date'] = start_date
    if end_date:
        session['end_date'] = end_date

    key_insights = request.form.get('key_insights')
    session['key_insights'] = key_insights


    return redirect(url_for('results'))  # go back to /report
                   
  
                

@app.route('/report', methods=['GET'])
def results():
    try:
        # Get session data
        data = get_session_data()
        df = data['df']
        base_url = data['base_url']
        holidays = data.get('holidays', [])
        authors = data['authors']

        # Defaults
        selected_category = request.args.get('category_type', 'Activity')
        selected_summary_type = request.args.get('summary_type', 'Issue Summary')
        summary_sort_by = request.args.get('summary_sort_by', 'Author')  # New sort parameter
        working_hours = float(request.args.get('working_hours', 8))
        working_days = request.args.getlist('working_days') or ['Monday','Tuesday','Wednesday','Thursday','Friday']
        leave_days = float(request.args.get('leave_days', 0))
        holiday_days = float(request.args.get('holiday_days', 0))
        custom_column = request.args.get('custom_column', '')

        # Get project name and logo from session
        project_name = session.get('project_name')
        logo_filename = session.get('logo_filename')
        start_date = session.get('start_date')
        end_date = session.get('end_date')
        key_insights = session.get('key_insights')

        # Default project name if not set
        if not project_name and 'Project Name' in df.columns and not df['Project Name'].empty:
            project_name = df['Project Name'].iloc[0]

        # Handle custom column selection
        if selected_category not in ['Activity', 'Label']:
            custom_column = selected_category
        elif selected_category == 'Custom' and custom_column:
            selected_category = custom_column

        # Get selected authors and store in session
        selected_authors = request.args.getlist('author')
        
        # Debug: Log selected authors from request
        print(f"Debug - Selected authors from request: {selected_authors}")
        
        # Clean up selected authors list to remove any duplicates and handle 'All' properly
        if selected_authors:
            if 'All' in selected_authors:
                # If All is selected along with other authors, ignore other authors
                selected_authors = ['All']
            else:
                # Remove duplicates while preserving order
                selected_authors = list(dict.fromkeys(selected_authors))
                if not selected_authors:
                    # If list becomes empty after removing duplicates, default to All
                    selected_authors = ['All']
        else:
            # Default to 'All' if no authors selected
            selected_authors = ['All']
            
        print(f"Debug - Selected authors after processing: {selected_authors}")
        session['selected_authors'] = selected_authors

        # Store category and summary selections in session
        session['selected_category'] = selected_category
        session['selected_summary_type'] = selected_summary_type
        

        # Check if this is imported timesheet data
        is_reverse_timesheet = base_url == "https://imported-timesheet/"
        
        # Filter dataframe based on selected authors
        if selected_authors != ['All']:
            display_df = df[df['Author'].isin(selected_authors)].copy()
        else:
            display_df = df.copy()

        # Store the list of displayed authors for UI
        displayed_authors = sorted(display_df['Author'].unique().tolist())
        session['displayed_authors'] = displayed_authors

        # Calculate capacity and category hours once for all selected authors
        capacity_list, category_hours_list = availableCapacity(
            display_df.copy(), None, working_hours, working_days, holidays, selected_category
        )
        _, category_totals_df = process_timesheet(
            display_df.copy(), base_url, selected_category, working_days, holidays
        )
        summary_df_for_ui = process_summary(display_df.copy(), selected_category, selected_summary_type, summary_sort_by,is_reverse_timesheet)
        overtime_data = calculate_overtime_hours(
            display_df.copy(), leave_days, 0, working_hours, working_days, holidays
        )
        weekly_overtime_data = calculate_weekly_overtime(
            display_df.copy(), working_hours, working_days, holidays
        )

        # Build per-author overtime table if "All" selected
        overtime_list = []
        if selected_authors == ['All'] or 'All' in selected_authors:
            overtime_list = calculate_overtime_list(
                display_df.copy(), leave_days, working_hours, working_days, holidays
            )

        category_total_sum = category_totals_df['Hours spent'].sum() if not category_totals_df.empty else 0
        unique_story_count, unique_task_count = getStoryAndTaskCount(display_df.copy())
        author_task_list = getAuthorSubtaskCount(display_df.copy())

        start_date_str = format_date(start_date)
        end_date_str = format_date(end_date)

        # Debug: Log authors to check for duplicates
        print(f"Debug - Authors list: {authors}")
        print(f"Debug - Authors count: {len(authors)}")
        print(f"Debug - Authors set: {set(authors)}")
        print(f"Debug - Authors set count: {len(set(authors))}")


        print(f'Debug - Rendering Reverse Timesheet: {is_reverse_timesheet}. base_url: {base_url}')
        return render_template(
            'index.html',
            processed=True,
            authors=authors,
            selected_authors=selected_authors,
            selected_category=selected_category,
            selected_summary_type=selected_summary_type,
            summary_sort_by=summary_sort_by,  # Add sort parameter to template
            is_reverse_timesheet=is_reverse_timesheet,  # Add flag for template
            leave_days=leave_days,
            holiday_days=holiday_days,
            working_hours=working_hours,
            working_days=working_days,
            category_totals=category_totals_df.to_dict(orient='records'),
            category_total_sum=category_total_sum,
            summary_data=summary_df_for_ui.to_dict(orient='records'),
            overtime_data=overtime_data,
            weekly_overtime_data=weekly_overtime_data,
            holidays=holidays,
            unique_task_count=unique_task_count,
            unique_story_count=unique_story_count,
            capacity_list=capacity_list,
            category_hours_list=category_hours_list,
            project_name=project_name,
            logo_filename=logo_filename,
            start_date=start_date_str,
            end_date=end_date_str,
            key_insights=key_insights,
            overtime_list=overtime_list,
            author_task_data=author_task_list
        )
    except DataNotFoundError:
        return redirect(url_for('index'))


   
    #    # NEW: build per-author overtime table if "All" selected
    # overtime_list = []
    # if selected_author == "All":
    #     overtime_list = calculate_overtime_list(display_df.copy(), leave_days, working_hours, working_days, holidays)

    # category_total_sum = category_totals_df['Hours spent'].sum() if not category_totals_df.empty else 0
    # unique_story_count, unique_task_count = getStoryAndTaskCount(display_df.copy())
    # author_task_list = getAuthorSubtaskCount(display_df.copy())
    
    # start_date_str = format_date(start_date)
    # end_date_str = format_date(end_date)
    # print("start_date:", start_date)
    # print("end_date:", end_date)
    # return render_template(
    #     'index.html',
    #     processed=True,
    #     authors=session.get('user_authors', []),
    #     selected_author=selected_author,
    #     selected_category=selected_category,
    #     selected_summary_type=selected_summary_type,
    #     leave_days=leave_days,
    #     holiday_days=holiday_days,
    #     working_hours=working_hours,
    #     working_days=working_days,
    #     category_totals=category_totals_df.to_dict(orient='records'),
    #     category_total_sum=category_total_sum,
    #     summary_data=summary_df_for_ui.to_dict(orient='records'),
    #     overtime_data=overtime_data,
    #     weekly_overtime_data=weekly_overtime_data,
    #     holidays=holidays,
    #     unique_task_count=unique_task_count,
    #     unique_story_count=unique_story_count,
    #     capacity_list=capacity_list,
    #     category_hours_list=category_hours_list,
    #     project_name=project_name,
    #     logo_filename=logo_filename,
    #     start_date= start_date_str,
    #     end_date= end_date_str,
    #     key_insights = key_insights,
    #     overtime_list=overtime_list,  
    #     author_task_data=author_task_list,
    #     # burnout_data=burnout_data,

    # )

@app.route('/download_bulk/<report_type>')
def download_bulk_reports(report_type):
    """
    Downloads individual Excel files for each author as a ZIP archive
    Creates separate Excel files for each author
    """
    try:
        # Get session data
        data = get_session_data()
        df = data['df']
        base_url = data['base_url']
        holidays = data.get('holidays', [])
        
        # Get selected authors from URL params or session
        selected_authors = request.args.getlist('author') or session.get('selected_authors', ['All'])
        
        # If specific authors are selected, filter the dataframe
        if selected_authors and 'All' not in selected_authors:
            df = df[df['Author'].isin(selected_authors)].copy()
        
        selected_category = request.args.get('category_type', 'Activity')
        leave_days = float(request.args.get('leave_days', 0))
        holiday_days = float(request.args.get('holiday_days', 0))
        working_hours = float(request.args.get('working_hours', 8))
        working_days_param = request.args.get('working_days', '')
        working_days = working_days_param.split(',') if working_days_param else ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        
        # Create a ZIP file containing individual Excel files
        import zipfile
        import tempfile
        import os
        
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for author in df['Author'].unique():
                    # Filter data for this author
                    author_df = df[df['Author'] == author].copy()
                    
                    if report_type == 'detailed':
                        output_df, _ = process_timesheet(
                            author_df, base_url, selected_category,
                            working_days, holidays
                        )
                        
                        # Create individual Excel file for this author
                        excel_buffer = BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            output_df.to_excel(writer, index=False, sheet_name='Timesheet')
                        
                        # Clean author name for filename
                        clean_author_name = str(author).replace('/', '_').replace('\\', '_').replace('[', '').replace(']', '').replace('*', '').replace('?', '').replace(':', '').replace('<', '').replace('>', '').replace('|', '')
                        filename = f"{clean_author_name}_timesheet.xlsx"
                        
                        # Add the Excel file to ZIP
                        excel_buffer.seek(0)
                        zip_file.writestr(filename, excel_buffer.getvalue())
            
            zip_buffer.seek(0)
            download_name = f"individual_timesheets_{len(df['Author'].unique())}_authors.zip"
            
            return send_file(
                zip_buffer,
                as_attachment=True,
                download_name=download_name,
                mimetype='application/zip'
            )
    except DataNotFoundError:
        return redirect(url_for('index'))
    
    # Get session data
    df_json = session.get('user_df')
    if not df_json:
        return redirect(url_for('index'))
    df = pd.read_json(df_json)
    base_url = session.get('user_base_url', '')

    # Get all unique authors
    all_authors = df['Author'].unique()
    
    # Create a ZIP file containing individual Excel files
    import zipfile
    import tempfile
    import os
    
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for author in all_authors:
                # Filter data for this author
                author_df = df[df['Author'] == author].copy()
                
                if report_type == 'detailed':
                    output_df, _ = process_timesheet(author_df, base_url, selected_category, working_days, holidays)
                    
                    # Create individual Excel file for this author
                    excel_buffer = BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        output_df.to_excel(writer, index=False, sheet_name='Timesheet')
                    
                    # Clean author name for filename
                    clean_author_name = str(author).replace('/', '_').replace('\\', '_').replace('[', '').replace(']', '').replace('*', '').replace('?', '').replace(':', '').replace('<', '').replace('>', '').replace('|', '')
                    filename = f"{clean_author_name}_timesheet.xlsx"
                    
                    # Add the Excel file to ZIP
                    excel_buffer.seek(0)
                    zip_file.writestr(filename, excel_buffer.getvalue())
        
        zip_buffer.seek(0)
        download_name = f"individual_timesheets_{len(all_authors)}_authors.zip"
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=download_name,
            mimetype='application/zip'
        )

@app.route('/download/<report_type>')
def download_report(report_type):
    """
    Generates and serves a specific report file on demand.
    The data is filtered based on the 'author' query parameter.
    """
    try:
        # Get session data
        data = get_session_data()
        df = data['df']
        base_url = data['base_url']
        holidays = data.get('holidays', [])

        # Get selected authors from URL params or session
        selected_authors = request.args.getlist('author') or session.get('selected_authors', ['All'])
        selected_category = request.args.get('category_type', session.get('selected_category', 'Activity'))
        selected_summary_type = request.args.get('summary_type', session.get('selected_summary_type', 'Issue Summary'))
        custom_column = request.args.get('custom_column', '')
        leave_days = float(request.args.get('leave_days', 0))
        holiday_days = float(request.args.get('holiday_days', 0))
        working_hours = float(request.args.get('working_hours', 8))
        
        # Handle working_days parameter
        working_days_param = request.args.get('working_days', '')
        working_days = (
            working_days_param.split(',')
            if isinstance(working_days_param, str) and working_days_param
            else ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        )

        # Handle custom column selection
        if selected_category not in ['Activity', 'Label'] and selected_category != 'Activity':
            custom_column = selected_category
        elif selected_category == 'Custom' and custom_column:
            selected_category = custom_column

        # Filter dataframe based on selected authors
        if selected_authors and 'All' not in selected_authors:
            display_df = df[df['Author'].isin(selected_authors)].copy()
            author_label = ", ".join(selected_authors)
        else:
            display_df = df.copy()
            author_label = "All"

        # Generate the requested file
        if report_type == 'detailed':
            output_df, _ = process_timesheet(
                display_df.copy(), base_url, selected_category,
                working_days, holidays
            )
            file_io = BytesIO()
            output_df.to_excel(file_io, index=False, sheet_name='Detailed Timesheet')
            file_io.seek(0)
            download_name = session.get('fileName', 'timesheet.xlsx').rsplit('.', 1)[0] + "_detailed.xlsx"
        
        elif report_type == 'summary':
            summary_sort_by = request.args.get('summary_sort_by', 'Author')
            summary_df = process_summary(display_df.copy(), selected_category, selected_summary_type, summary_sort_by)
            file_io = BytesIO()
            summary_df.to_excel(file_io, index=False, sheet_name='Summary Report')
            file_io.seek(0)
            download_name = "jira_summary.xlsx"
        
        elif report_type == 'sprint_closure':
            file_io = process_sprint_closure_report(display_df.copy(), selected_summary_type)
            download_name = "sprint_closure_report.xlsx"
        
        else:
            return "Invalid report type", 404

        return send_file(
            file_io,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except DataNotFoundError:
        return redirect(url_for('index'))
    
    # # Handle custom column selection - check if it's a custom column name directly
    # if selected_category not in ['Activity', 'Label'] and selected_category != 'Activity':
    #     # This means selected_category contains the custom column name
    #     custom_column = selected_category
    # elif selected_category == 'Custom' and custom_column:
    #     selected_category = custom_column
    
    # # Debug logging
    # print(f"Debug Download - selected_category: {selected_category}, custom_column: {custom_column}, summary_type: {selected_summary_type}")
    # print(selected_author)

    # # Filter the main DataFrame based on selection
    # # Get session data
    # df_json = session.get('user_df')
    # if not df_json:
    #     return redirect(url_for('index'))
    # df = pd.read_json(df_json)
    # base_url = session.get('user_base_url', '')

    # if selected_author == 'All':
    #     display_df = df
    # else:
    #     display_df = df[df['Author'] == selected_author].copy()

    # # Generate the requested file with category type
    # if report_type == 'detailed':
    #     output_df, _ = process_timesheet(display_df, base_url, selected_category, working_days, holidays)
    #     file_io = BytesIO()
    #     output_df.to_excel(file_io, index=False, sheet_name='Detailed Timesheet')
    #     file_io.seek(0)
    #     download_name = original_filename.rsplit('.', 1)[0] + "_detailed.xlsx"
    # elif report_type == 'summary':
    #     summary_df = process_summary(display_df, selected_category, selected_summary_type)
    #     file_io = BytesIO()
    #     summary_df.to_excel(file_io, index=False, sheet_name='Summary Report')
    #     file_io.seek(0)
    #     download_name = "jira_summary.xlsx"
    # elif report_type == 'sprint_closure':
    #     file_io = process_sprint_closure_report(display_df, selected_summary_type)
    #     download_name = "sprint_closure_report.xlsx"
    # else:
    #     return "Invalid report type", 404

    # return send_file(
    #     file_io,
    #     as_attachment=True,
    #     download_name=download_name,
    #     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    # )

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5005)
