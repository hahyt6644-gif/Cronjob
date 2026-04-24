import os
import uuid
import requests
import json
from flask import Flask, render_template_string, request, redirect, url_for, flash, send_file
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = 'super_secret_key_change_me'

# The text/JSON file where we will save the data
CONFIG_FILE = 'cron_config.json'

# Initialize the Scheduler
scheduler = BackgroundScheduler()
scheduler.start()

def ping_target(url):
    """The background task that hits the user's URL."""
    try:
        response = requests.get(url, timeout=10)
        print(f"Success: Pinged {url} - Status Code: {response.status_code}")
    except Exception as e:
        print(f"Failed: Could not reach {url} - Error: {str(e)}")

def init_file():
    """Create the config file if it doesn't exist."""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({}, f)

def load_jobs_from_file():
    """Read the config file and load jobs into the scheduler on startup."""
    init_file()
    with open(CONFIG_FILE, 'r') as f:
        jobs = json.load(f)
        
    for job_id, data in jobs.items():
        url = data['url']
        value = data['value']
        schedule_type = data['schedule_type']
        
        if schedule_type == 'minutes':
            scheduler.add_job(ping_target, 'interval', minutes=value, args=[url], id=job_id, replace_existing=True)
        elif schedule_type == 'hours':
            scheduler.add_job(ping_target, 'interval', hours=value, args=[url], id=job_id, replace_existing=True)

# Load jobs immediately when the app starts
load_jobs_from_file()

def save_job_to_file(job_id, url, schedule_type, value):
    """Save a new job to the text file."""
    with open(CONFIG_FILE, 'r') as f:
        jobs = json.load(f)
    
    jobs[job_id] = {
        'url': url,
        'schedule_type': schedule_type,
        'value': value
    }
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(jobs, f, indent=4)

def delete_job_from_file(job_id):
    """Remove a job from the text file."""
    with open(CONFIG_FILE, 'r') as f:
        jobs = json.load(f)
        
    if job_id in jobs:
        del jobs[job_id]
        
    with open(CONFIG_FILE, 'w') as f:
        json.dump(jobs, f, indent=4)


# Embedded HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File-Based Cron Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">

<div class="container mt-5">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>Cronjob Manager</h2>
        <a href="/download" class="btn btn-outline-primary">⬇️ Download Config File</a>
    </div>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
          </div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <div class="card shadow-sm mb-5">
        <div class="card-header bg-dark text-white">
            <h5 class="card-title mb-0">Add a New Cronjob</h5>
        </div>
        <div class="card-body">
            <form action="/add" method="POST" class="row g-3 align-items-center">
                <div class="col-md-5">
                    <label for="url" class="form-label">Target URL</label>
                    <input type="url" class="form-control" id="url" name="url" placeholder="https://api.yourdomain.com/task" required>
                </div>
                <div class="col-md-3">
                    <label for="value" class="form-label">Interval Value</label>
                    <input type="number" class="form-control" id="value" name="value" value="1" min="1" required>
                </div>
                <div class="col-md-3">
                    <label for="schedule_type" class="form-label">Time Unit</label>
                    <select id="schedule_type" name="schedule_type" class="form-select">
                        <option value="minutes">Minutes</option>
                        <option value="hours">Hours</option>
                    </select>
                </div>
                <div class="col-md-1 d-flex align-items-end mt-auto">
                    <button type="submit" class="btn btn-success w-100">Add</button>
                </div>
            </form>
        </div>
    </div>

    <h4 class="mb-3">Active Jobs (Saved in File)</h4>
    <div class="card shadow-sm">
        <div class="card-body p-0">
            <table class="table table-hover mb-0">
                <thead class="table-light">
                    <tr>
                        <th>Target URL</th>
                        <th>Schedule</th>
                        <th>Next Run (UTC)</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for job in jobs %}
                    <tr>
                        <td class="text-break">{{ job.url }}</td>
                        <td>{{ job.trigger }}</td>
                        <td>{{ job.next_run }}</td>
                        <td>
                            <a href="/delete/{{ job.id }}" class="btn btn-sm btn-danger" onclick="return confirm('Delete this job?');">Delete</a>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="4" class="text-center py-4 text-muted">No active cronjobs. Add one above!</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route('/')
def index():
    # Read the text file to get the list of jobs
    init_file()
    with open(CONFIG_FILE, 'r') as f:
        saved_jobs = json.load(f)
        
    job_list = []
    for job_id, data in saved_jobs.items():
        # Ask APScheduler when this job is running next
        job_instance = scheduler.get_job(job_id)
        next_run = job_instance.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job_instance and job_instance.next_run_time else 'Unknown'
        
        job_list.append({
            'id': job_id,
            'url': data['url'],
            'trigger': f"Every {data['value']} {data['schedule_type']}",
            'next_run': next_run
        })
        
    return render_template_string(HTML_TEMPLATE, jobs=job_list)

@app.route('/add', methods=['POST'])
def add_job():
    url = request.form.get('url')
    schedule_type = request.form.get('schedule_type')
    value = int(request.form.get('value', 1))

    if not url:
        flash("A target URL is required!", "danger")
        return redirect(url_for('index'))

    job_id = str(uuid.uuid4())

    # 1. Add to the active scheduler
    if schedule_type == 'minutes':
        scheduler.add_job(ping_target, 'interval', minutes=value, args=[url], id=job_id)
    elif schedule_type == 'hours':
        scheduler.add_job(ping_target, 'interval', hours=value, args=[url], id=job_id)

    # 2. Save the data to the text file
    save_job_to_file(job_id, url, schedule_type, value)

    flash(f"Successfully added cron job. Data saved to file.", "success")
    return redirect(url_for('index'))

@app.route('/delete/<job_id>')
def delete_job(job_id):
    try:
        # 1. Remove from active scheduler
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        
        # 2. Delete from text file
        delete_job_from_file(job_id)
        
        flash("Job successfully deleted and removed from file.", "success")
    except Exception as e:
        flash(f"Error deleting job: {str(e)}", "danger")
        
    return redirect(url_for('index'))

@app.route('/download')
def download_config():
    """Allows the user to download the cron configuration file."""
    init_file()
    return send_file(CONFIG_FILE, as_attachment=True, download_name="cron_jobs_backup.txt")

if __name__ == '__main__':
    # Binds correctly for both Local and Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
