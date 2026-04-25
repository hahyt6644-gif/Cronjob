import os
import json
import uuid
import time
import threading
import subprocess
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'super_secret_key_change_me'

CONFIG_FILE = 'cron_config.json'
LOG_FILE = 'cron_logs.txt'

# --- LOGGING SYSTEM ---
def log_message(msg):
    """Writes to terminal and saves to a log file for the Admin Panel."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {msg}\n"
    print(log_entry.strip()) # Print to Render console
    
    # Append to file
    with open(LOG_FILE, 'a') as f:
        f.write(log_entry)
        
    # Keep only the last 100 lines so the file doesn't get huge
    try:
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
        if len(lines) > 100:
            with open(LOG_FILE, 'w') as f:
                f.writelines(lines[-100:])
    except Exception:
        pass

# --- BACKGROUND WORKER (NO EXTERNAL LIBS) ---
def background_worker():
    """Runs infinitely in the background, executing cURL when time is up."""
    log_message("System: Background worker initialized and running.")
    job_last_run = {} # Tracks { 'job_id': timestamp_of_last_run }
    
    while True:
        try:
            # 1. Load jobs from config
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    jobs = json.load(f)
            else:
                jobs = {}
            
            current_time = time.time()
            
            # 2. Check each job
            for job_id, job_data in jobs.items():
                url = job_data['url']
                value = int(job_data['value'])
                schedule_type = job_data['schedule_type']
                
                # If new job, set last run to 0 so it runs immediately
                if job_id not in job_last_run:
                    job_last_run[job_id] = 0 
                    
                last_run = job_last_run[job_id]
                interval_seconds = value * 60 if schedule_type == 'minutes' else value * 3600
                
                # 3. If enough time has passed, fire cURL!
                if (current_time - last_run) >= interval_seconds:
                    log_message(f"Firing cURL -> {url}")
                    try:
                        # System cURL command: grabs HTTP status code, discards body, 15s timeout
                        result = subprocess.run(
                            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', url],
                            capture_output=True, text=True, timeout=15
                        )
                        status_code = result.stdout.strip()
                        log_message(f"Success: HTTP {status_code} from {url}")
                    except subprocess.TimeoutExpired:
                        log_message(f"Error: cURL timeout (15s) for {url}")
                    except Exception as e:
                        log_message(f"Error: cURL failed - {str(e)}")
                        
                    # Update the run time
                    job_last_run[job_id] = current_time
                    
        except Exception as e:
            log_message(f"System Error in worker loop: {str(e)}")
            
        # Wait exactly 60 seconds before checking the list again
        time.sleep(60)

# Start the background worker thread immediately
worker_thread = threading.Thread(target=background_worker, daemon=True)
worker_thread.start()

# --- HELPER FUNCTIONS ---
def init_file():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({}, f)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w') as f:
            f.write("System log initialized...\n")

# --- UI TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Native cURL Cron Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .terminal { background-color: #1e1e1e; color: #00ff00; font-family: monospace; height: 300px; overflow-y: auto; padding: 15px; border-radius: 5px; }
    </style>
</head>
<body class="bg-light">
<div class="container mt-4">
    <h2 class="mb-4">Native cURL Cron Manager</h2>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert alert-{{ category }} alert-dismissible fade show">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <div class="row">
        <div class="col-md-12 mb-4">
            <div class="card shadow-sm">
                <div class="card-header bg-dark text-white"><b>Add a New Cronjob</b></div>
                <div class="card-body">
                    <form action="/add" method="POST" class="row g-3">
                        <div class="col-md-6">
                            <input type="url" class="form-control" name="url" placeholder="https://api.yourdomain.com/task" required>
                        </div>
                        <div class="col-md-2">
                            <input type="number" class="form-control" name="value" value="1" min="1" required>
                        </div>
                        <div class="col-md-2">
                            <select name="schedule_type" class="form-select">
                                <option value="minutes">Minutes</option>
                                <option value="hours">Hours</option>
                            </select>
                        </div>
                        <div class="col-md-2">
                            <button type="submit" class="btn btn-success w-100">Add Job</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <div class="row">
        <div class="col-md-6 mb-4">
            <h4 class="mb-2">Active Jobs</h4>
            <div class="card shadow-sm">
                <table class="table mb-0">
                    <thead class="table-light">
                        <tr><th>URL</th><th>Schedule</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                        {% for job in jobs %}
                        <tr>
                            <td class="text-break" style="max-width: 200px;">{{ job.url }}</td>
                            <td>Every {{ job.value }} {{ job.schedule_type }}</td>
                            <td><a href="/delete/{{ job.id }}" class="btn btn-sm btn-danger">Del</a></td>
                        </tr>
                        {% else %}
                        <tr><td colspan="3" class="text-center text-muted py-3">No jobs running.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="col-md-6 mb-4">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h4 class="mb-0">System Logs</h4>
                <a href="/clear_logs" class="btn btn-sm btn-outline-secondary">Clear Logs</a>
            </div>
            <div class="terminal" id="logWindow">
                {{ logs | safe }}
            </div>
        </div>
    </div>
</div>
<script>
    // Auto-scroll terminal to bottom
    var logWindow = document.getElementById("logWindow");
    logWindow.scrollTop = logWindow.scrollHeight;
    
    // Auto-refresh page every 30 seconds to update logs
    setTimeout(function(){ location.reload(); }, 30000);
</script>
</body>
</html>
"""

# --- ROUTES ---
@app.route('/')
def index():
    init_file()
    
    # Load Jobs
    with open(CONFIG_FILE, 'r') as f:
        saved_jobs = json.load(f)
    job_list = [{'id': k, 'url': v['url'], 'value': v['value'], 'schedule_type': v['schedule_type']} for k, v in saved_jobs.items()]
    
    # Load Logs
    logs = "No logs yet."
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            logs = f.read().replace('\n', '<br>')
            
    return render_template_string(HTML_TEMPLATE, jobs=job_list, logs=logs)

@app.route('/add', methods=['POST'])
def add_job():
    url = request.form.get('url')
    schedule_type = request.form.get('schedule_type')
    value = request.form.get('value')
    
    init_file()
    with open(CONFIG_FILE, 'r') as f:
        jobs = json.load(f)
        
    job_id = str(uuid.uuid4())[:8] # Short ID
    jobs[job_id] = {'url': url, 'schedule_type': schedule_type, 'value': value}
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(jobs, f, indent=4)
        
    log_message(f"Admin: Added new job -> {url}")
    flash("Job added successfully!", "success")
    return redirect(url_for('index'))

@app.route('/delete/<job_id>')
def delete_job(job_id):
    with open(CONFIG_FILE, 'r') as f:
        jobs = json.load(f)
        
    if job_id in jobs:
        url = jobs[job_id]['url']
        del jobs[job_id]
        with open(CONFIG_FILE, 'w') as f:
            json.dump(jobs, f, indent=4)
        log_message(f"Admin: Deleted job -> {url}")
        
    flash("Job deleted.", "success")
    return redirect(url_for('index'))

@app.route('/clear_logs')
def clear_logs():
    with open(LOG_FILE, 'w') as f:
        f.write("System logs cleared...\n")
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
