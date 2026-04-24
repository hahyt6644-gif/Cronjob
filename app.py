import os
import uuid
import requests
from flask import Flask, render_template_string, request, redirect, url_for, flash
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

app = Flask(__name__)
app.secret_key = 'replace_this_with_a_secure_secret_key'

# Database Configuration (SQLite for local, PostgreSQL for Render)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///cronjobs.sqlite')

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configure APScheduler to use the database to remember jobs across server restarts
jobstores = {
    'default': SQLAlchemyJobStore(url=DATABASE_URL)
}

scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start()

def ping_target(url):
    """The background task that hits the user's URL."""
    try:
        response = requests.get(url, timeout=10)
        print(f"Success: Pinged {url} - Status Code: {response.status_code}")
    except Exception as e:
        print(f"Failed: Could not reach {url} - Error: {str(e)}")


# Embedded HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Professional Cron Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">

<div class="container mt-5">
    <h2 class="mb-4">Cronjob Manager</h2>

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
        <div class="card-header bg-primary text-white">
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

    <h4 class="mb-3">Active Jobs</h4>
    <div class="card shadow-sm">
        <div class="card-body p-0">
            <table class="table table-hover mb-0">
                <thead class="table-dark">
                    <tr>
                        <th>Target URL</th>
                        <th>Schedule Trigger</th>
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
                        <td colspan="4" class="text-center py-4 text-muted">No active cronjobs running. Add one above!</td>
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
    # Fetch all active jobs from the database
    jobs = scheduler.get_jobs()
    job_list = []
    for job in jobs:
        job_list.append({
            'id': job.id,
            'url': job.args[0] if job.args else 'Unknown URL',
            'trigger': str(job.trigger),
            'next_run': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else 'Paused'
        })
    # Render the embedded string instead of an external file
    return render_template_string(HTML_TEMPLATE, jobs=job_list)

@app.route('/add', methods=['POST'])
def add_job():
    url = request.form.get('url')
    schedule_type = request.form.get('schedule_type')
    value = int(request.form.get('value', 1))

    if not url:
        flash("A target URL is required!", "danger")
        return redirect(url_for('index'))

    # Generate a unique ID for the job
    job_id = str(uuid.uuid4())

    # Add the job to the scheduler based on user selection
    if schedule_type == 'minutes':
        scheduler.add_job(ping_target, 'interval', minutes=value, args=[url], id=job_id)
    elif schedule_type == 'hours':
        scheduler.add_job(ping_target, 'interval', hours=value, args=[url], id=job_id)

    flash(f"Successfully added cron job for {url} (Runs every {value} {schedule_type}).", "success")
    return redirect(url_for('index'))

@app.route('/delete/<job_id>')
def delete_job(job_id):
    try:
        scheduler.remove_job(job_id)
        flash("Job successfully deleted.", "success")
    except Exception:
        flash("Error deleting job or job not found.", "danger")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
