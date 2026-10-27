
from flask import Flask, render_template, request, redirect, url_for, flash
import boto3
import os
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import json

load_dotenv()


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "student-project-demo-key")

BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

def get_s3():
    if not BUCKET_NAME:
        return None
    return boto3.client("s3", region_name=AWS_REGION)
# Load study planner tasks
def load_tasks():
    try:
        with open("tasks.json", "r", encoding="utf-8") as task_file:
            return json.load(task_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# Save study planner tasks
def save_tasks(tasks):
    with open("tasks.json", "w", encoding="utf-8") as task_file:
        json.dump(tasks, task_file, indent=4)



def get_file_category(filename):
    name = os.path.basename(filename).lower()
    normalized_name = name.replace("-", "_").replace(" ", "_")
    extension = os.path.splitext(filename)[1].lower()

    # Identify the student's subject from the filename
    subject_keywords = {
        "Computer Networks": [
            "computer_network", "network_layer", "transport_layer",
            "application_layer", "cn_"
        ],
        "Cloud Computing": [
            "cloud_computing", "cloud", "virtualization",
            "hadoop", "salesforce"
        ],
        "Theory of Computation": [
            "theory_of_computation", "automata", "toc_",
            "pda", "dfa", "nfa", "cyk", "cnf"
        ],
        "Artificial Intelligence": [
            "artificial_intelligence", "chatbot",
            "8_queens", "backtracking", "astar", "ai_"
        ]
    }

    for subject, keywords in subject_keywords.items():
        for keyword in keywords:
            if normalized_name.startswith(keyword) or f"_{keyword}" in normalized_name:
                return subject

    # If no subject matches, use the existing file-type categories
    categories = {
        "Documents": [".pdf", ".doc", ".docx", ".txt", ".ppt", ".pptx", ".xls", ".xlsx"],
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"],
        "Code": [".py", ".java", ".c", ".cpp", ".js", ".html", ".css", ".sql"],
        "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "Audio": [".mp3", ".wav", ".aac", ".ogg"],
        "Video": [".mp4", ".mkv", ".avi", ".mov"]
    }

    for category, extensions in categories.items():
        if extension in extensions:
            return category

    return "Other"



@app.route("/")
def index():
    files = []
    message = ""

    # Load the student profile
    try:
        with open("profile.json", "r", encoding="utf-8") as profile_file:
            profile = json.load(profile_file)
    except (FileNotFoundError, json.JSONDecodeError):
        profile = {
            "student_name": "Demo Student",
            "academic_year": "2026-27",
            "branch": "Computer Engineering",
            "current_semester": 5
        }

    # Retrieve files from AWS S3
    try:
        s3 = get_s3()
        if s3:
            response = s3.list_objects_v2(Bucket=BUCKET_NAME)

            for item in response.get("Contents", []):
                filename = item["Key"]
                files.append({
                    "name": filename,
                    "size": item["Size"],
                    "category": get_file_category(filename)
                })
        else:
            message = "Cloud storage is not configured yet."

    except (ClientError, NoCredentialsError) as error:
        message = "AWS connection is not ready. Check your configuration."
        print("AWS error:", error)

    # Calculate dashboard statistics
    total_files = len(files)
    total_storage = sum(file["size"] for file in files)
    
    storage_limit = 100 * 1024 * 1024  # 100 MB in bytes
    storage_percentage = min((total_storage / storage_limit) * 100, 100)
    storage_percentage = round(storage_percentage, 1)


    storage_kb = round(total_storage / 1024, 2)
    storage_mb = round(total_storage / (1024 * 1024), 2)

    category_counts = {}

    for file in files:
        category = file["category"]
        category_counts[category] = category_counts.get(category, 0) + 1


    # Calculate subject-wise analytics
    subjects = [
        "Computer Networks",
        "Cloud Computing",
        "Theory of Computation",
        "Artificial Intelligence"
    ]

    subject_counts = {subject: 0 for subject in subjects}

    for file in files:
        if file["category"] in subject_counts:
            subject_counts[file["category"]] += 1
    return render_template(
    "index.html",
    files=files,
    message=message,
    profile=profile,
    tasks=load_tasks(),
    total_files=total_files,
    total_storage=total_storage,
    storage_kb=storage_kb,
    storage_mb=storage_mb,
    category_counts=category_counts,
    subject_counts=subject_counts,
    storage_limit=storage_limit,
    storage_percentage=storage_percentage
)

@app.route("/upload", methods=["POST"])
def upload():
    uploaded_file = request.files.get("file")

    if not uploaded_file or not uploaded_file.filename:
        flash("Please choose a file first.")
        return redirect(url_for("index"))

    filename = secure_filename(uploaded_file.filename)
    if not filename:
        flash("Invalid filename.")
        return redirect(url_for("index"))

    try:
        s3 = get_s3()
        if not s3:
            flash("Please configure your private S3 bucket first.")
        else:
            s3.upload_fileobj(uploaded_file, BUCKET_NAME, filename)
            flash("File uploaded to cloud storage successfully!")
    except (ClientError, NoCredentialsError) as error:
        print("AWS upload error:", error)
        flash("Upload failed. Check AWS configuration and permissions.")

    return redirect(url_for("index"))

@app.route("/download/<path:filename>")
def download(filename):
    from flask import Response

    try:
        s3 = get_s3()
        if not s3:
            flash("Cloud storage is not configured.")
            return redirect(url_for("index"))

        safe_name = secure_filename(filename)
        response = s3.get_object(Bucket=BUCKET_NAME, Key=safe_name)
        return Response(
            response["Body"].read(),
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}"',
                "Content-Type": response.get(
                    "ContentType", "application/octet-stream"
                )
            }
        )
    except (ClientError, NoCredentialsError) as error:
        print("AWS download error:", error)
        flash("Download failed. Check the file and AWS permissions.")
        return redirect(url_for("index"))

@app.route("/delete/<path:filename>", methods=["POST"])
def delete(filename):
    try:
        s3 = get_s3()
        if not s3:
            flash("Cloud storage is not configured.")
        else:
            safe_name = secure_filename(filename)
            s3.delete_object(Bucket=BUCKET_NAME, Key=safe_name)
            flash("File deleted from cloud storage.")
    except (ClientError, NoCredentialsError) as error:
        print("AWS delete error:", error)
        flash("Delete failed. Check AWS permissions.")

    return redirect(url_for("index"))
# Study Planner: Add a task
@app.route("/add-task", methods=["POST"])
def add_task():
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    due_date = request.form.get("due_date", "").strip()

    allowed_subjects = [
        "Computer Networks",
        "Cloud Computing",
        "Theory of Computation",
        "Artificial Intelligence",
        "Other"
    ]

    if not title or len(title) > 150:
        flash("Enter a task title of 1–150 characters.")
        return redirect(url_for("index"))

    if subject not in allowed_subjects:
        flash("Please select a valid subject.")
        return redirect(url_for("index"))

    if not due_date:
        flash("Please select a due date.")
        return redirect(url_for("index"))

    tasks = load_tasks()

    tasks.append({
        "id": max([task.get("id", 0) for task in tasks], default=0) + 1,
        "title": title,
        "subject": subject,
        "due_date": due_date,
        "completed": False
    })

    save_tasks(tasks)
    flash("Study task added successfully!")
    return redirect(url_for("index"))


# Study Planner: Mark a task complete or incomplete
@app.route("/toggle-task/<int:task_id>", methods=["POST"])
def toggle_task(task_id):
    tasks = load_tasks()

    for task in tasks:
        if task.get("id") == task_id:
            task["completed"] = not task.get("completed", False)
            save_tasks(tasks)
            flash("Task status updated!")
            break
    else:
        flash("Task not found.")

    return redirect(url_for("index"))


# Study Planner: Delete a task
@app.route("/delete-task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    tasks = load_tasks()
    updated_tasks = [task for task in tasks if task.get("id") != task_id]

    if len(updated_tasks) == len(tasks):
        flash("Task not found.")
    else:
        save_tasks(updated_tasks)
        flash("Study task deleted.")

    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
