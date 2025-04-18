import os
import logging
import atexit
import time  # For sleep in retry loops
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
import smtplib
import os
import logging
import atexit
import time  # For sleep in retry loops
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from certificate_gen import generate_internship_offer, generate_certificate

# Base directory of the project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ------------------------------------------------------------------------------
# Load environment variables from .env
# ------------------------------------------------------------------------------
load_dotenv()

# ------------------------------------------------------------------------------
# Configure logging
# ------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Initialize Flask App and SQLAlchemy using PostgreSQL
# ------------------------------------------------------------------------------
app = Flask(__name__, static_folder="public_html", template_folder="public_html")
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "fallback-secret"),
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL"),  # e.g., postgresql://user:password@localhost/dbname
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=15),
    SCHEDULER_API_ENABLED=False,
    SCHEDULER_ENABLED=True,
)
application = app
db = SQLAlchemy(app)

# ------------------------------------------------------------------------------
# Database Model
# ------------------------------------------------------------------------------
class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False, index=True)
    internship_function = db.Column(db.String(100), nullable=False)
    telegram_contact = db.Column(db.String(50))
    whatsapp = db.Column(db.String(50))
    payment_status = db.Column(db.String(20), default='pending')
    payment_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    internship_start_date = db.Column(db.DateTime)
    internship_duration = db.Column(db.Integer)
    internship_week = db.Column(db.Integer, default=1)
    last_email_sent = db.Column(db.DateTime, nullable=True)
    completion_email_sent = db.Column(db.Boolean, default=False)
    internship_details_email_sent = db.Column(db.Boolean, default=False)
    internship_loi_email_sent = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Student {self.email}>'

# ------------------------------------------------------------------------------
# Initialize Database
# ------------------------------------------------------------------------------
with app.app_context():
    db.create_all()
    logger.info("Database tables created or verified")

# ------------------------------------------------------------------------------
# Flask Routes
# ------------------------------------------------------------------------------
@app.route('/')
def home():
    logger.info("Home page accessed")
    return render_template('index.html')

@app.route('/form')
def form():
    logger.info("Form page accessed")
    return render_template('form.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        payment_id = data.get("razorpay_payment_id")
        name = data.get("name")
        email = data.get("email")
        internship_function = data.get("domain")

        form_data = {
            "name": name,
            "email": email,
            "internship_function": internship_function,
            "whatsapp": data.get("whatsapp"),
            "telegram_contact": data.get("telegram_contact"),
            "payment_id": payment_id,
            "payment_status": "paid",
            "internship_start_date": datetime.now(),
            "internship_duration": 1
        }

        # Save to database with retry logic
        for attempt in range(3):
            try:
                db.session.begin()
                new_student = Student(**form_data)
                db.session.add(new_student)
                db.session.commit()
                break
            except Exception as e:
                db.session.rollback()
                if attempt == 2:
                    logger.error("Database commit failed after multiple attempts.")
                    raise e
                time.sleep(1)

        send_confirmation_email(email, name, internship_function)
        session.pop('form_data', None)

        return jsonify({"status": "success", "redirect_url": "/thank-you"})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing payment/registration: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/thank-you')
def thank_you():
    return render_template('success.html')

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(error):
    return render_template('500.html'), 500

# ------------------------------------------------------------------------------
# Email Sending with Improved Reliability (Retry Logic)
# ------------------------------------------------------------------------------
def send_email(to_email, subject, body, attachment_paths=None):
    """
    Sends an email via SMTP with a retry loop.
    """
    try:
        sender_email = os.getenv("EMAIL_USER")
        password = os.getenv("EMAIL_PASSWORD")

        if not sender_email or not password:
            raise ValueError("Missing email credentials (EMAIL_USER, EMAIL_PASSWORD)")

        # Construct message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # Handle attachments (supports single path or list)
        if attachment_paths:
            attachments = attachment_paths if isinstance(attachment_paths, list) else [attachment_paths]
            for attachment_path in attachments:
                if attachment_path and os.path.isfile(attachment_path):
                    with open(attachment_path, "rb") as f:
                        file_data = f.read()
                    attachment = MIMEText(file_data, "base64", _charset="utf-8")
                    attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                    message.attach(attachment)

        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(sender_email, password)
                    server.send_message(message)
                logger.info(f"Email sent to {to_email}")
                break  # Break on success
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Email failed to {to_email}: {str(e)}")
                if attempt == max_attempts - 1:
                    raise
                time.sleep(2)
    except Exception as e:
        logger.error(f"Final failure sending email to {to_email}: {str(e)}")
        raise

def send_confirmation_email(email, name, internship_function):
    """
    Sends a registration confirmation email.
    """
    subject = "Internship Registration Successful."
    body = f""" 
Dear {name},

Congratulations! Your registration for the {internship_function} at SkillNova has been successfully received.

Our team will review your application, and we will get back to you shortly with the next steps.
Please keep an eye on your inbox for further updates.

If you have any questions in the meantime, feel free to reach out to us at contact.skillnova@gmail.com.

Looking forward to having you on board!

Best regards,
SkillNova
contact.skillnova@gmail.com 
"""
    send_email(email, subject, body)

def send_internship_details_email(email, name, internship_function):
    """
    Sends internship details email (with attached PDF) after a delay.
    """
    pdf_path_dir = {
        "Web Development": "web-dev.pdf",
        "Android App Development": "",
        "Data Science": "data-science.pdf",
        "Java Programming": "java-prog.pdf",
        "Python Programming": "Python.pdf",
        "C++ Programming": "c++prog.pdf",
        "UI/UX Design": "ui-ux.pdf",
        "Artificial Intelligence": "ai.pdf",
        "Machine Learning": "ML.pdf"
    }
    
    subject = "SkillNova Virtual Internship - Detailed Instructions"
    body = f"""
Dear {name},

Congratulations! Your registration for the SkillNova Virtual Internship Program has been successfully confirmed. We are excited to have you on board and look forward to helping you gain hands-on experience in your chosen domain.

Internship Details:
  • Internship Mode: 100% Virtual
  • Duration: 4 Weeks
  • Domain: {internship_function}
  • Work Structure: Weekly Assignments & Real-World Projects
  • Guidance & Mentorship: Support from industry professionals
  • Certificate of Completion: Upon successful completion

Your Learning Experience:
  • Work on structured assignments tailored to {internship_function}
  • Gain hands-on experience with real-world projects
  • Develop industry-relevant skills to enhance your career prospects
  • Receive guidance from experienced mentors

Project & Assignment Details:
Attached you will find a PDF with details of the projects and assignments.

Please review the attached document carefully. For any queries, contact us at contact.skillnova@gmail.com.

Best Regards,
Best regards,
SkillNova
contact.skillnova@gmail.com 
"""
    internship = pdf_path_dir.get(internship_function, "")
    pdf_path = os.path.join(BASE_DIR, 'Task_pdf', internship) if internship else None
    send_email(email, subject, body, attachment_paths=pdf_path)

def send_internship_loi_email(email, name, internship_function):
    """
    Sends an internship offer letter email.
    """
    subject = "SkillNova Virtual Internship - Offer Letter"
    body = f"""Dear {name},

Congratulations on your registration for the SkillNova Virtual Internship Program.
Please find attached your Offer Letter for the internship in {internship_function}.

Best Regards,
SkillNova Team
contact.skillnova@gmail.com
"""
    generate_internship_offer(name=name, internship=internship_function)
    attachment_path = os.path.join(BASE_DIR, 'gen_certificate/generated_Internship_Offer_Letter.jpg')
    send_email(email, subject, body, attachment_paths=attachment_path)

# ------------------------------------------------------------------------------
# Scheduled Tasks
# ------------------------------------------------------------------------------
def send_weekly_emails():
    """Send weekly internship emails to students with a paid status, ensuring a one-week gap."""
    week_tasks = {
        "Web Development": ["https://docs.google.com/forms/d/e/1FAIpQLScheF-rGdySwRWrg-ARZoxUi1ncwrYnLdWtua3nx9U3TfNocg/viewform", "", "", ""],
        "Android App Development": ["https://docs.google.com/forms/d/e/1FAIpQLSeojl8IdBaergAV62-sEYboyDssugt86WvjOJZGZUdPkhKT7A/viewform", "", "", ""],
        "Data Science": ["https://docs.google.com/forms/d/e/1FAIpQLSeMHIkZ1MDPsGSgHyA6waUw4xvnnNj9C-rb1qAcUhdjboeubA/viewform", "", "", ""],
        "Java Programming": ["", "", "", ""],
        "Python Programming": ["https://docs.google.com/forms/d/e/1FAIpQLSc0POGnXXdgBoJwry0c5zMT3cHJ5NFaZQB2pi4Iv3n55kS-jA/viewform", "", "", ""],
        "C++ Programming": ["https://docs.google.com/forms/d/e/1FAIpQLSdoIrEig_S3hcppQcLn1DJe2BN7n7JTzTyJMLDmZYQOlmE5oA/viewform", "", "", ""],
        "UI/UX Design": ["", "", "", ""],
        "Artificial Intelligence": ["https://docs.google.com/forms/d/e/1FAIpQLSexkJ8XfsKvrDs3RIhAU0T6Om-urNKLERXSPUBKiN3YoNbMDg/viewform", "", "", ""],
        "Machine Learning": ["https://docs.google.com/forms/d/e/1FAIpQLSeImUGzaT735c9aDF6g_XYEz35kVf8KGk2CCzDXYWIBeOgFqA/viewform", "", "", ""]
    }
    
    with app.app_context():
        try:
            students = Student.query.filter_by(payment_status="paid").all()
            now = datetime.now()

            for student in students:
                if student.internship_week > 4:
                    logger.info(f"Skipping {student.email}: Internship completed.")
                    continue

                # Ensure at least 7 days gap between emails
                if student.last_email_sent and (now - student.last_email_sent).days < 7:
                    logger.info(f"Skipping {student.email}: Less than 7 days since the last email.")
                    continue

                subject = "Weekly Internship Update"
                task_details = week_tasks.get(student.internship_function, [""])[student.internship_week - 1]
                body = f"Hi {student.name},\n\nHere are your tasks: {task_details}"
                send_email(student.email, subject, body)
                logger.info(f"Sent weekly email to {student.email}")

                student.internship_week += 1
                student.last_email_sent = now
                db.session.commit()

        except Exception as e:
            logger.error(f"Error in send_weekly_emails: {str(e)}", exc_info=True)

def send_completion_emails():
    with app.app_context():
        try:
            now = datetime.now()
            students = Student.query.filter_by(payment_status='paid', completion_email_sent=False).all()
            for student in students:
                if student.internship_start_date:
                    end_date = student.internship_start_date + timedelta(days=28 * student.internship_duration)
                    if now >= end_date:
                        subject = "Internship Completion Certificate"
                        body = f"Congratulations {student.name}!\n\nYou've successfully completed your internship."
                        generate_certificate(name=student.name, internship=student.internship_function)
                        send_email(
                            student.email, subject, body,
                            attachment_paths=os.path.join(BASE_DIR, 'gen_certificate/generated_certificate.jpg')
                        )
                        student.completion_email_sent = True
                        db.session.commit()
        except Exception as e:
            logger.error(f"Completion emails failed: {str(e)}")

def cleanup_old_entries():
    with app.app_context():
        try:
            two_months_ago = datetime.now(timezone.utc) - timedelta(days=60)
            Student.query.filter(Student.created_at < two_months_ago).delete(synchronize_session=False)
            db.session.commit()
            logger.info("Old student entries have been cleaned up.")
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
            db.session.rollback()

def send_internship_details_if_due():
    with app.app_context():
        try:
            now = datetime.now()
            students = Student.query.filter_by(payment_status='paid', internship_details_email_sent=False).all()
            for student in students:
                if student.internship_start_date:
                    due_time = student.internship_start_date + timedelta(hours=10)
                    if now >= due_time:
                        send_internship_details_email(student.email, student.name, student.internship_function)
                        student.internship_details_email_sent = True
                        db.session.commit()
        except Exception as e:
            logger.error(f"Error in send_internship_details_if_due: {str(e)}")

def send_internship_loi_if_due():
    with app.app_context():
        try:
            now = datetime.now()
            students = Student.query.filter_by(payment_status='paid', internship_loi_email_sent=False).all()
            for student in students:
                if student.internship_start_date:
                    due_time = student.internship_start_date + timedelta(seconds=40)
                    if now >= due_time:
                        send_internship_loi_email(student.email, student.name, student.internship_function)
                        student.internship_loi_email_sent = True
                        db.session.commit()
        except Exception as e:
            logger.error(f"Error in send_internship_loi_if_due: {str(e)}")

# ------------------------------------------------------------------------------
# Scheduler Setup using a Persistent Job Store (PostgreSQL)
# ------------------------------------------------------------------------------
jobstores = {
    "default": SQLAlchemyJobStore(url=os.getenv("DATABASE_URL"))
}
executors = {
    "default": ThreadPoolExecutor(max_workers=10)
}
scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors)

def test_job():
    logger.info("Test job executed successfully!")

def start_scheduler():
    if app.config["SCHEDULER_ENABLED"]:
        # Each job now has a misfire grace time, coalescing, and a max instance limit.
        scheduler.add_job(
            id='send_internship_details_if_due',
            func=send_internship_details_if_due,
            trigger='cron',
            hour=18,
            minute=30,
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1
        )
        scheduler.add_job(
            id='send_internship_loi_if_due',
            func=send_internship_loi_if_due,
            trigger='cron',
            hour=18,
            minute=30,
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1
        )
        scheduler.add_job(
            id='weekly_emails',
            func=send_weekly_emails,
            trigger='cron',
            hour=18,
            minute=30,
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1
        )
        scheduler.add_job(
            id='cleanup',
            func=cleanup_old_entries,
            trigger='cron',
            hour=2,
            minute=0,
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1
        )
        # Uncomment to add a periodic test job if needed
        # scheduler.add_job(
        #     func=test_job,
        #     trigger="interval",
        #     minutes=1,
        #     id="test_job",
        #     replace_existing=True,
        #     misfire_grace_time=300,
        #     coalesce=True,
        #     max_instances=1
        # )
        scheduler.start()
        logger.info("APScheduler started with PostgreSQL persistence and robust settings.")
    else:
        logger.info("APScheduler is not started")

start_scheduler()
# ------------------------------------------------------------------------------
# Main Entry Point
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    logger.info("Scheduled jobs: %s", scheduler.get_jobs())
    # For production, use a WSGI server (e.g., Gunicorn) with multiple workers.
    app.run(debug=False)
    atexit.register(lambda: scheduler.shutdown())

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from certificate_gen import generate_internship_offer, generate_certificate

# Base directory of the project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ------------------------------------------------------------------------------
# Load environment variables from .env
# ------------------------------------------------------------------------------
load_dotenv()

# ------------------------------------------------------------------------------
# Configure logging
# ------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Initialize Flask App and SQLAlchemy using PostgreSQL
# ------------------------------------------------------------------------------
app = Flask(__name__, static_folder="public_html", template_folder="public_html")
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "fallback-secret"),
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL"),  # e.g., postgresql://user:password@localhost/dbname
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=15),
    SCHEDULER_API_ENABLED=False,
    SCHEDULER_ENABLED=True,
)
application = app
db = SQLAlchemy(app)

# ------------------------------------------------------------------------------
# Database Model
# ------------------------------------------------------------------------------
class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False, index=True)
    internship_function = db.Column(db.String(100), nullable=False)
    telegram_contact = db.Column(db.String(50))
    whatsapp = db.Column(db.String(50))
    payment_status = db.Column(db.String(20), default='pending')
    payment_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    internship_start_date = db.Column(db.DateTime)
    internship_duration = db.Column(db.Integer)
    internship_week = db.Column(db.Integer, default=1)
    last_email_sent = db.Column(db.DateTime, nullable=True)
    completion_email_sent = db.Column(db.Boolean, default=False)
    internship_details_email_sent = db.Column(db.Boolean, default=False)
    internship_loi_email_sent = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Student {self.email}>'

# ------------------------------------------------------------------------------
# Initialize Database
# ------------------------------------------------------------------------------
with app.app_context():
    db.create_all()
    logger.info("Database tables created or verified")

# ------------------------------------------------------------------------------
# Flask Routes
# ------------------------------------------------------------------------------
@app.route('/')
def home():
    logger.info("Home page accessed")
    return render_template('index.html')

@app.route('/form')
def form():
    logger.info("Form page accessed")
    return render_template('form.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        payment_id = data.get("razorpay_payment_id")
        name = data.get("name")
        email = data.get("email")
        internship_function = data.get("domain")

        form_data = {
            "name": name,
            "email": email,
            "internship_function": internship_function,
            "whatsapp": data.get("whatsapp"),
            "telegram_contact": data.get("telegram_contact"),
            "payment_id": payment_id,
            "payment_status": "paid",
            "internship_start_date": datetime.now(),
            "internship_duration": 1
        }

        # Save to database with retry logic
        for attempt in range(3):
            try:
                db.session.begin()
                new_student = Student(**form_data)
                db.session.add(new_student)
                db.session.commit()
                break
            except Exception as e:
                db.session.rollback()
                if attempt == 2:
                    logger.error("Database commit failed after multiple attempts.")
                    raise e
                time.sleep(1)

        send_confirmation_email(email, name, internship_function)
        session.pop('form_data', None)

        return jsonify({"status": "success", "redirect_url": "/thank-you"})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing payment/registration: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/thank-you')
def thank_you():
    return render_template('success.html')

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(error):
    return render_template('500.html'), 500

# ------------------------------------------------------------------------------
# Email Sending with Improved Reliability (Retry Logic)
# ------------------------------------------------------------------------------
def send_email(to_email, subject, body, attachment_paths=None):
    """
    Sends an email via SMTP with a retry loop.
    """
    try:
        sender_email = os.getenv("EMAIL_USER")
        password = os.getenv("EMAIL_PASSWORD")

        if not sender_email or not password:
            raise ValueError("Missing email credentials (EMAIL_USER, EMAIL_PASSWORD)")

        # Construct message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # Handle attachments (supports single path or list)
        if attachment_paths:
            attachments = attachment_paths if isinstance(attachment_paths, list) else [attachment_paths]
            for attachment_path in attachments:
                if attachment_path and os.path.isfile(attachment_path):
                    with open(attachment_path, "rb") as f:
                        file_data = f.read()
                    attachment = MIMEText(file_data, "base64", _charset="utf-8")
                    attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                    message.attach(attachment)

        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(sender_email, password)
                    server.send_message(message)
                logger.info(f"Email sent to {to_email}")
                break  # Break on success
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Email failed to {to_email}: {str(e)}")
                if attempt == max_attempts - 1:
                    raise
                time.sleep(2)
    except Exception as e:
        logger.error(f"Final failure sending email to {to_email}: {str(e)}")
        raise

def send_confirmation_email(email, name, internship_function):
    """
    Sends a registration confirmation email.
    """
    subject = "Internship Registration Successful."
    body = f""" 
Dear {name},

Congratulations! Your registration for the {internship_function} at SkillNova has been successfully received.

Our team will review your application, and we will get back to you shortly with the next steps.
Please keep an eye on your inbox for further updates.

If you have any questions in the meantime, feel free to reach out to us at contact.skillnova@gmail.com.

Looking forward to having you on board!

Best regards,
SkillNova
contact.skillnova@gmail.com 
"""
    send_email(email, subject, body)

def send_internship_details_email(email, name, internship_function):
    """
    Sends internship details email (with attached PDF) after a delay.
    """
    pdf_path_dir = {
        "Web Development": "web-dev.pdf",
        "Android App Development": "",
        "Data Science": "data-science.pdf",
        "Java Programming": "java-prog.pdf",
        "Python Programming": "Python.pdf",
        "C++ Programming": "c++prog.pdf",
        "UI/UX Design": "ui-ux.pdf",
        "Artificial Intelligence": "ai.pdf",
        "Machine Learning": "ML.pdf"
    }
    
    subject = "SkillNova Virtual Internship - Detailed Instructions"
    body = f"""
Dear {name},

Congratulations! Your registration for the SkillNova Virtual Internship Program has been successfully confirmed. We are excited to have you on board and look forward to helping you gain hands-on experience in your chosen domain.

Internship Details:
  • Internship Mode: 100% Virtual
  • Duration: 4 Weeks
  • Domain: {internship_function}
  • Work Structure: Weekly Assignments & Real-World Projects
  • Guidance & Mentorship: Support from industry professionals
  • Certificate of Completion: Upon successful completion

Your Learning Experience:
  • Work on structured assignments tailored to {internship_function}
  • Gain hands-on experience with real-world projects
  • Develop industry-relevant skills to enhance your career prospects
  • Receive guidance from experienced mentors

Project & Assignment Details:
Attached you will find a PDF with details of the projects and assignments.

Please review the attached document carefully. For any queries, contact us at contact.skillnova@gmail.com.

Best Regards,
Best regards,
SkillNova
contact.skillnova@gmail.com 
"""
    internship = pdf_path_dir.get(internship_function, "")
    pdf_path = os.path.join(BASE_DIR, 'Task_pdf', internship) if internship else None
    send_email(email, subject, body, attachment_paths=pdf_path)

def send_internship_loi_email(email, name, internship_function):
    """
    Sends an internship offer letter email.
    """
    subject = "SkillNova Virtual Internship - Offer Letter"
    body = f"""Dear {name},

Congratulations on your registration for the SkillNova Virtual Internship Program.
Please find attached your Offer Letter for the internship in {internship_function}.

Best Regards,
SkillNova Team
contact.skillnova@gmail.com
"""
    generate_internship_offer(name=name, internship=internship_function)
    attachment_path = os.path.join(BASE_DIR, 'gen_certificate/generated_Internship_Offer_Letter.jpg')
    send_email(email, subject, body, attachment_paths=attachment_path)

# ------------------------------------------------------------------------------
# Scheduled Tasks
# ------------------------------------------------------------------------------
def send_weekly_emails():
    """Send weekly internship emails to students with a paid status, ensuring a one-week gap."""
    week_tasks = {
        "Web Development": ["https://docs.google.com/forms/d/e/1FAIpQLScheF-rGdySwRWrg-ARZoxUi1ncwrYnLdWtua3nx9U3TfNocg/viewform", "", "", ""],
        "Android App Development": ["https://docs.google.com/forms/d/e/1FAIpQLSeojl8IdBaergAV62-sEYboyDssugt86WvjOJZGZUdPkhKT7A/viewform", "", "", ""],
        "Data Science": ["https://docs.google.com/forms/d/e/1FAIpQLSeMHIkZ1MDPsGSgHyA6waUw4xvnnNj9C-rb1qAcUhdjboeubA/viewform", "", "", ""],
        "Java Programming": ["", "", "", ""],
        "Python Programming": ["https://docs.google.com/forms/d/e/1FAIpQLSc0POGnXXdgBoJwry0c5zMT3cHJ5NFaZQB2pi4Iv3n55kS-jA/viewform", "", "", ""],
        "C++ Programming": ["https://docs.google.com/forms/d/e/1FAIpQLSdoIrEig_S3hcppQcLn1DJe2BN7n7JTzTyJMLDmZYQOlmE5oA/viewform", "", "", ""],
        "UI/UX Design": ["", "", "", ""],
        "Artificial Intelligence": ["https://docs.google.com/forms/d/e/1FAIpQLSexkJ8XfsKvrDs3RIhAU0T6Om-urNKLERXSPUBKiN3YoNbMDg/viewform", "", "", ""],
        "Machine Learning": ["https://docs.google.com/forms/d/e/1FAIpQLSeImUGzaT735c9aDF6g_XYEz35kVf8KGk2CCzDXYWIBeOgFqA/viewform", "", "", ""]
    }
    
    with app.app_context():
        try:
            students = Student.query.filter_by(payment_status="paid").all()
            now = datetime.now()

            for student in students:
                if student.internship_week > 4:
                    logger.info(f"Skipping {student.email}: Internship completed.")
                    continue

                # Ensure at least 7 days gap between emails
                if student.last_email_sent and (now - student.last_email_sent).days < 7:
                    logger.info(f"Skipping {student.email}: Less than 7 days since the last email.")
                    continue

                subject = "Weekly Internship Update"
                task_details = week_tasks.get(student.internship_function, [""])[student.internship_week - 1]
                body = f"Hi {student.name},\n\nHere are your tasks: {task_details}"
                send_email(student.email, subject, body)
                logger.info(f"Sent weekly email to {student.email}")

                student.internship_week += 1
                student.last_email_sent = now
                db.session.commit()

        except Exception as e:
            logger.error(f"Error in send_weekly_emails: {str(e)}", exc_info=True)

def send_completion_emails():
    with app.app_context():
        try:
            now = datetime.now()
            students = Student.query.filter_by(payment_status='paid', completion_email_sent=False).all()
            for student in students:
                if student.internship_start_date:
                    end_date = student.internship_start_date + timedelta(days=28 * student.internship_duration)
                    if now >= end_date:
                        subject = "Internship Completion Certificate"
                        body = f"Congratulations {student.name}!\n\nYou've successfully completed your internship."
                        generate_certificate(name=student.name, internship=student.internship_function)
                        send_email(
                            student.email, subject, body,
                            attachment_paths=os.path.join(BASE_DIR, 'gen_certificate/generated_certificate.jpg')
                        )
                        student.completion_email_sent = True
                        db.session.commit()
        except Exception as e:
            logger.error(f"Completion emails failed: {str(e)}")

def cleanup_old_entries():
    with app.app_context():
        try:
            two_months_ago = datetime.now(timezone.utc) - timedelta(days=60)
            Student.query.filter(Student.created_at < two_months_ago).delete(synchronize_session=False)
            db.session.commit()
            logger.info("Old student entries have been cleaned up.")
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
            db.session.rollback()

def send_internship_details_if_due():
    with app.app_context():
        try:
            now = datetime.now()
            students = Student.query.filter_by(payment_status='paid', internship_details_email_sent=False).all()
            for student in students:
                if student.internship_start_date:
                    due_time = student.internship_start_date + timedelta(hours=10)
                    if now >= due_time:
                        send_internship_details_email(student.email, student.name, student.internship_function)
                        student.internship_details_email_sent = True
                        db.session.commit()
        except Exception as e:
            logger.error(f"Error in send_internship_details_if_due: {str(e)}")

def send_internship_loi_if_due():
    with app.app_context():
        try:
            now = datetime.now()
            students = Student.query.filter_by(payment_status='paid', internship_loi_email_sent=False).all()
            for student in students:
                if student.internship_start_date:
                    due_time = student.internship_start_date + timedelta(seconds=40)
                    if now >= due_time:
                        send_internship_loi_email(student.email, student.name, student.internship_function)
                        student.internship_loi_email_sent = True
                        db.session.commit()
        except Exception as e:
            logger.error(f"Error in send_internship_loi_if_due: {str(e)}")

# ------------------------------------------------------------------------------
# Scheduler Setup using a Persistent Job Store (PostgreSQL)
# ------------------------------------------------------------------------------
jobstores = {
    "default": SQLAlchemyJobStore(url=os.getenv("DATABASE_URL"))
}
executors = {
    "default": ThreadPoolExecutor(max_workers=10)
}
scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors)

def test_job():
    logger.info("Test job executed successfully!")

def start_scheduler():
    if app.config["SCHEDULER_ENABLED"]:
        # Each job now has a misfire grace time, coalescing, and a max instance limit.
        scheduler.add_job(
            id='send_internship_details_if_due',
            func=send_internship_details_if_due,
            trigger='cron',
            hour=18,
            minute=30,
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1
        )
        scheduler.add_job(
            id='send_internship_loi_if_due',
            func=send_internship_loi_if_due,
            trigger='cron',
            hour=18,
            minute=30,
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1
        )
        scheduler.add_job(
            id='weekly_emails',
            func=send_weekly_emails,
            trigger='cron',
            hour=18,
            minute=30,
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1
        )
        scheduler.add_job(
            id='cleanup',
            func=cleanup_old_entries,
            trigger='cron',
            hour=2,
            minute=0,
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1
        )
        # Uncomment to add a periodic test job if needed
        # scheduler.add_job(
        #     func=test_job,
        #     trigger="interval",
        #     minutes=1,
        #     id="test_job",
        #     replace_existing=True,
        #     misfire_grace_time=300,
        #     coalesce=True,
        #     max_instances=1
        # )
        scheduler.start()
        logger.info("APScheduler started with PostgreSQL persistence and robust settings.")
    else:
        logger.info("APScheduler is not started")

start_scheduler()
# ------------------------------------------------------------------------------
# Main Entry Point
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    logger.info("Scheduled jobs: %s", scheduler.get_jobs())
    # For production, use a WSGI server (e.g., Gunicorn) with multiple workers.
    app.run(debug=False)
    atexit.register(lambda: scheduler.shutdown())
