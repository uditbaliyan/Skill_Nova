from operator import and_
import os
import logging
import atexit
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import razorpay

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy globally
db = SQLAlchemy()

# Razorpay client initialization
client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY"), os.getenv("RAZORPAY_SECRET")))

# Configuration class
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SCHEDULER_API_ENABLED = False  # Disable scheduler API for security
    SCHEDULER_JOB_DEFAULTS = {'coalesce': True, 'max_instances': 1}
    SCHEDULER_ENABLED = True
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance/students.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=15)
    RAZORPAY_KEY = os.getenv("RAZORPAY_KEY")
    RAZORPAY_SECRET = os.getenv("RAZORPAY_SECRET")

# Database model
class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    internship_function = db.Column(db.String(100), nullable=False)
    telegram_contact = db.Column(db.String(50))
    whatsapp = db.Column(db.String(50))
    payment_status = db.Column(db.String(20), default='pending')
    payment_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    internship_start_date = db.Column(db.DateTime)
    internship_duration = db.Column(db.Integer)
    completion_email_sent = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Student {self.email}>'

# Application factory function
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize SQLAlchemy with this app
    db.init_app(app)

    # Register routes
    @app.route('/', methods=['GET'])
    def home():
        logger.info("Home page accessed")
        return render_template('index.html')

    @app.route('/form', methods=['GET'])
    def form():
        logger.info("Form page accessed")
        return render_template('form.html')

    @app.route('/submit', methods=['POST'])
    def submit():
        try:
            data = request.json  # Get JSON data from frontend

            # Extract Payment Details
            payment_id = data.get("razorpay_payment_id")
            order_id = data.get("razorpay_order_id")
            signature = data.get("razorpay_signature")

            # Verify Payment Signature
            params = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            # if not client.utility.verify_payment_signature(params):
            #     return jsonify({"status": "error", "message": "Invalid payment signature"}), 400

            # Extract User Registration Details
            form_data = {
                "name": data.get("name"),
                "email": data.get("email"),
                "internship_function": data.get("domain"),
                "whatsapp": data.get("whatsapp"),
                "telegram_contact": data.get("telegram_contact"),
                "payment_id": payment_id,
                "payment_status": "paid",
                "internship_start_date": datetime.now(),
                "internship_duration": 1
            }

            # Save Data in Database with Retry Logic
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
                        raise e

            email=data.get("email")
            name=data.get("name")
            internship_function=data.get("domain")
            # Optionally, send confirmation email here...
            send_confirmation_email(email=email, name=name, internship_function=internship_function)

            print(f"{email}{name}{internship_function}")
            # Clear Session Data After Successful Registration (if used)
            session.pop('form_data', None)
            session.pop('razorpay_order_id', None)

            return jsonify({"status": "success", "redirect_url": "/thank-you"})


        except Exception as e:
            db.session.rollback()
            logger.error(f"Error processing payment: {str(e)}")
            return jsonify({"status": "error", "message": "Error processing payment: " + str(e)}), 500

    @app.route('/payment-failed', methods=['POST'])
    def payment_failed():
        try:
            data = request.json
            email = data.get("email")
            error_code = data.get("error_code")
            error_description = data.get("error_description")
            logger.warning(f"Payment failed for {email}. Error: {error_code} - {error_description}")
            return jsonify({"status": "error", "message": "Payment failed, please try again."}), 400
        except Exception as e:
            logger.error(f"Error logging failed payment: {str(e)}")
            return jsonify({"status": "error", "message": "Could not log failed payment."}), 500

    @app.route('/thank-you')
    def thank_you():
        return render_template('success.html')

    # Create all tables
    with app.app_context():
        db.create_all()
        logger.info("Database tables created")

    return app

# Create the app instance using the factory
app = create_app()

# CLI commands
@app.cli.command('init-db')
def init_db():
    """Initialize the database."""
    with app.app_context():
        db.create_all()
        logger.info("Database initialized")

@app.cli.command('send-test-email')
def send_test_email():
    try:
        # Example test email function; implement your own as needed.
        logger.info("Sending test email...")
    except Exception as e:
        logger.error(f"Failed to send test email: {str(e)}")

# Scheduler functions (if used) can be registered here.






def send_email(to_email, subject, body):
    try:
        sender_email = os.getenv("EMAIL_USER")
        password = os.getenv("EMAIL_PASSWORD")

        if not sender_email or not password:
            raise ValueError("Missing email credentials")

        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(os.getenv("SMTP_SERVER", "smtp.gmail.com"), 
             int(os.getenv("SMTP_PORT", 587))) as server:
            server.starttls()
            server.login(sender_email, password)
            server.send_message(message)
        logger.info(f"Email sent to {to_email}")

    except Exception as e:
        logger.error(f"Email failed to {to_email}: {str(e)}")
        raise

def send_confirmation_email(email, name, internship_function):
    try:
        send_email(
            email,
            "Internship Registration Confirmation",
            f"Hello {name},\n\nYour internship in {internship_function} has been confirmed!"
        )
    except Exception as e:
        logger.error(f"Email failed for {email}: {str(e)}")

def send_test_emails():
    with app.app_context():
        try:
            logger.info("=== Starting test email job ===")
            students = Student.query.all()
            
            if not students:
                logger.info("No students found in database")
                return
                
            for student in students:
                logger.info(f"Processing student: {student.email}")
                try:
                    send_email(
                        to_email=student.email,
                        subject="Test Email - System Check",
                        body=f"Hello {student.name},\n\nThis is a scheduled test email."
                    )
                    logger.info(f"Email successfully sent to {student.email}")
                except Exception as e:
                    logger.error(f"Email failed for {student.email}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Test email job failed: {str(e)}")
        finally:
            logger.info("=== Completed test email job ===")

def send_daily_tasks():
    with scheduler.app_context():
        try:
            students = Student.query.filter(
                and_(
                    Student.payment_status == "paid",
                    Student.completion_email_sent == False
                )
            ).all()
            
            for student in students:
                try:
                    send_email(
                        student.email,
                        "Your Daily Internship Tasks",
                        f"Hi {student.name},\n\nHere are your tasks for today..."
                    )
                except Exception as e:
                    logger.error(f"Daily email failed for {student.email}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Daily tasks failed: {str(e)}")

def send_completion_emails():
    with scheduler.app_context():
        try:
            students = Student.query.filter(
                and_(
                    Student.payment_status == "paid",
                    Student.completion_email_sent == False,
                    Student.internship_start_date <= datetime.utcnow() - timedelta(days=30 * student.internship_duration)
                )
            ).all()
            
            for student in students:
                try:
                    send_email(
                        student.email,
                        "Internship Completion Certificate",
                        f"Congratulations {student.name}!\n\nYou've successfully completed your internship."
                    )
                    student.completion_email_sent = True
                    db.session.commit()
                except Exception as e:
                    logger.error(f"Completion email failed for {student.email}: {str(e)}")
                    db.session.rollback()
                    
        except Exception as e:
            logger.error(f"Completion emails failed: {str(e)}")

def cleanup_old_entries():
    with scheduler.app_context():
        try:
            two_months_ago = datetime.now(datetime.timezone.utc) - timedelta(days=60)
            old_students = Student.query.filter(
                Student.created_at < two_months_ago
            ).all()
            
            for student in old_students:
                db.session.delete(student)
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
            db.session.rollback()

def send_weekly_emails():
    with scheduler.app_context():
        try:
            students = Student.query.filter_by(payment_status="paid").all()
            for student in students:
                try:
                    send_email(
                        to_email=student.email,
                        subject="Weekly Internship Update",
                        body=f"Hi {student.name},\n\nHere are your tasks for this week..."
                    )
                except Exception as e:
                    logger.error(f"Failed to send weekly email to {student.email}: {str(e)}")
        except Exception as e:
            logger.error(f"Weekly emails task failed: {str(e)}")




def register_scheduler(sched):
    if Config.SCHEDULER_ENABLED and not os.environ.get('WERKZEUG_RUN_MAIN'):
        # Existing production jobs
        sched.add_job(id='weekly_emails', func=send_weekly_emails,trigger='cron', day_of_week='mon', hour=9)
        sched.add_job(id='cleanup', func=cleanup_old_entries, trigger='cron', day=1, hour=0)
        sched.add_job(id='daily_tasks', func=send_daily_tasks, trigger='cron', hour=9, minute=0)
        sched.add_job(id='completion_emails', func=send_completion_emails, trigger='cron', hour=10, minute=0)

        # Test job only in debug mode
        # if app.debug:
        #     sched.add_job(func=send_test_emails,trigger='interval',seconds=6)


def print_date_time():
    print("%A, %d. %B %Y %I:%M:%S %p")


if __name__ == '__main__':
    # Set up and start the scheduler if needed
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=lambda: logger.info("Scheduler job running"), trigger="interval", seconds=8000)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

    # Run the app
    app.run(debug=True, use_reloader=False)


