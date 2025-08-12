import socket
import pandas as pd
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from flask import Flask, render_template, request, send_file, redirect, url_for

app = Flask(__name__)

processed_file = None
summary_file = None
original_filename = None

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"
    finally:
        s.close()
    return local_ip


def process_timesheet(df, base_url):
    df['Start Date'] = pd.to_datetime(df['Start Date']).dt.tz_localize(None)
    df['Time'] = df['Start Date'].apply(lambda x: 'FullDay' if x.weekday() < 5 else 'Holiday')
    df['Date'] = pd.to_datetime(df['Start Date']).dt.strftime('%d/%b/%Y')

    df['Application/Project Name'] = df['Project Name']
    df['Activity/Task Done'] = df['Comment']
    df['Category'] = df['Labels']
    df['Ticket/Task #'] = df['Issue Key'].apply(lambda x: f"{base_url}{x}")

    df['Hours spent'] = df['Time Spent (seconds)'].apply(lambda x: round(x / 3600, 3))
    df['Start Time'] = df['Start Date'].dt.strftime('%I:%M %p')
    df['End Time'] = (df['Start Date'] + pd.to_timedelta(df['Time Spent (seconds)'], unit='s')).dt.strftime('%I:%M %p')

    df['Remarks for any additional information'] = ""
    df['Status'] = df['Issue Status']

    all_dates = pd.date_range(start=df['Start Date'].min(), end=df['Start Date'].max(), freq='D')
    weekends = all_dates[all_dates.weekday >= 5]
    worked_dates = df['Date'].unique()
    weekends_without_work = weekends[~weekends.strftime('%d/%b/%Y').isin(worked_dates)]

    weekend_df = pd.DataFrame({
        'Time': 'Holiday',
        'Date': weekends_without_work.strftime('%d/%b/%Y'),
        'Application/Project Name': 'M&M Sustenance',
        'Activity/Task Done': '',
        'Hours spent': 0,
        'Category': 'Weekend',
        'Ticket/Task #': '',
        'Start Time': '12:00 AM',
        'End Time': '',
        'Remarks for any additional information': '',
        'Status': ''
    })

    output_df = pd.concat([df, weekend_df], ignore_index=True)
    output_df['DateTime'] = pd.to_datetime(output_df['Date'] + ' ' + output_df['Start Time'],
                                           format='%d/%b/%Y %I:%M %p', errors='coerce')

    output_columns = [
        'Time', 'Date', 'Application/Project Name', 'Activity/Task Done', 'Hours spent',
        'Category', 'Ticket/Task #', 'Start Time', 'End Time', 'Remarks for any additional information', 'Status'
    ]
    output_df = output_df[output_columns + ['DateTime']]
    output_df = output_df.sort_values(by='DateTime', ascending=True).drop(columns=['DateTime'])

    category_totals = df.groupby('Category')['Hours spent'].sum().reset_index()

    return output_df, category_totals, df


def process_summary(df):
    summary_df = df.groupby(
        ['Labels', 'Issue Summary', 'Author', 'Issue Status'],
        as_index=False
    )['Time Spent (seconds)'].sum() 
 
    summary_df['Total Efforts (hrs)'] = round(summary_df['Time Spent (seconds)'] / 3600, 2)
    summary_df = summary_df.drop(columns=['Time Spent (seconds)'])
    return summary_df


def create_pie_chart(summary_df):
    fig, ax = plt.subplots()
    ax.pie(
        summary_df['Total Efforts (hrs)'],
        labels=summary_df['Issue Summary'],
        autopct='%1.1f%%',
        startangle=90
    )
    plt.tight_layout()
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close(fig)
    return base64.b64encode(img.getvalue()).decode('utf-8')

def format_hours(decimal_hours):
    hours = int(decimal_hours)
    minutes = int(round((decimal_hours - hours) * 60))
    if hours > 0 and minutes > 0:
        return f"{hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{minutes}m"


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process_file():
    global processed_file, summary_file, original_filename

    if 'file' not in request.files or 'base_url' not in request.form:
        return "Missing file or base URL", 400

    file = request.files['file']
    base_url = request.form['base_url']

    if file.filename == '':
        return "No selected file", 400

    if file:
        original_filename = file.filename
        df = pd.read_excel(file, parse_dates=['Start Date'])
        output_df, category_totals, raw_df = process_timesheet(df, base_url)
        summary_df = process_summary(raw_df)

        processed_file = BytesIO()
        with pd.ExcelWriter(processed_file, engine='xlsxwriter') as writer:
            output_df.to_excel(writer, index=False, sheet_name='Detailed Timesheet')
        processed_file.seek(0)

        summary_file = BytesIO()
        with pd.ExcelWriter(summary_file, engine='xlsxwriter') as writer:
            summary_df.to_excel(writer, index=False, sheet_name='Summary Report')
        summary_file.seek(0)

        # graph_base64 = create_pie_chart(summary_df)

        
        summary_display_df = summary_df.copy()
        if 'Hours spent' in summary_display_df.columns:
            summary_display_df['Hours spent'] = summary_display_df['Hours spent'].apply(format_hours)
        
        return render_template(
            'index.html',
            category_totals=category_totals.to_dict(orient='records'),
            summary_data=summary_df.to_dict(orient='records'),
            processed=True
        )   


@app.route('/download')
def download_file():
    if processed_file:
        download_name = original_filename.rsplit('.', 1)[0] + "_detailed.xlsx"
        return send_file(
            processed_file,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    return redirect(url_for('index'))


@app.route('/download_summary')
def download_summary():
    if summary_file:
        return send_file(
            summary_file,
            as_attachment=True,
            download_name="jira_summary.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    return redirect(url_for('index'))


if __name__ == '__main__':
    local_ip = get_local_ip()
    print(f"Running on {local_ip}:5000")
    app.run(host=local_ip, port=5000, debug=True)
