import os
import uuid
import logging
import secrets
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, has_request_context
from flask_sqlalchemy import SQLAlchemy
from flask_talisman import Talisman

from apscheduler.schedulers.background import BackgroundScheduler
import atexit

import razorpay
from razorpay.errors import BadRequestError, ServerError, SignatureVerificationError

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import validators
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime, timedelta
from sqlalchemy import and_

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure logging before creating app instances
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if has_request_context():  # Ensure we're inside a Flask request
            if hasattr(g, 'request_id'):
                record.request_id = g.request_id
            else:
                record.request_id = 'bg-' + str(uuid.uuid4())[:8]
        else:
            record.request_id = 'bg-' + str(uuid.uuid4())[:8]  # Background tasks
        return True

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")  # Use environment variable or fallback
    SCHEDULER_API_ENABLED = False  # Disable scheduler API for security
    SCHEDULER_JOB_DEFAULTS = {'coalesce': True, 'max_instances': 1}
    SCHEDULER_ENABLED = True
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance/students.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=15)
    RAZORPAY_KEY = os.getenv("RAZORPAY_KEY")
    RAZORPAY_SECRET = os.getenv("RAZORPAY_SECRET")

# Initialize extensions
db = SQLAlchemy()

def generate_nonce():
    """Generate a unique nonce for each request"""
    return secrets.token_urlsafe(16)

def get_csp_policy(nonce):
    """Generate the CSP policy with the provided nonce."""
    return {
        'default-src': "'self'",
        'script-src': [
            "'self'",
            "https://checkout.razorpay.com",
            "https://cdn.tailwindcss.com",
            "https://cdnjs.cloudflare.com",
            "https://cdn.jsdelivr.net",
            "https://unpkg.com",
            "'unsafe-eval'",  # Required for Alpine.js
            f"'nonce-{nonce}'"  # Dynamic nonce
        ],
        'style-src': [
            "'self'",
            "'unsafe-inline'",
            "https://cdnjs.cloudflare.com",
            "https://fonts.googleapis.com",
            "https://cdn.tailwindcss.com"
        ],
        'font-src': [
            "'self'",
            "data:",
            "https://fonts.gstatic.com",
            "https://cdnjs.cloudflare.com"  # For FontAwesome
        ],
        'img-src': [
            "'self'",
            "data:",
            "https://cdn-icons-png.flaticon.com",
            "https://unpkg.com",
            "https://*.razorpay.com"  # Razorpay logos
        ],
        'connect-src': [
            "'self'",
            "https://api.razorpay.com",
            "https://checkout.razorpay.com",
            "https://cdn.jsdelivr.net",
            "https://unpkg.com"
        ],
        'frame-src': [
            "https://checkout.razorpay.com"
        ]
    }

# Database models
class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    internship_function = db.Column(db.String(100), nullable=False)
    telegram_contact = db.Column(db.String(50))
    whatsapp = db.Column(db.String(50))
    payment_status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    internship_start_date = db.Column(db.DateTime)
    internship_duration = db.Column(db.Integer)  # Duration in months
    completion_email_sent = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Student {self.email}>'

# Helper functions
def init_razorpay():
    try:
        return razorpay.Client(auth=(Config.RAZORPAY_KEY, Config.RAZORPAY_SECRET))
    except Exception as e:
        logger.error(f"Failed to initialize Razorpay client: {str(e)}")
        raise

def validate_email(email):
    return validators.email(email) and 3 <= len(email) <= 150

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

# Routes and views
def register_blueprints(app):

    @app.before_request
    def set_request_context():
        g.request_id = session.get('request_id', str(uuid.uuid4()))
        session['request_id'] = g.request_id
        session.modified = True

    @app.route('/', methods=['GET'])
    def home():
        logger.info("Home page accessed")
        try:
            return render_template('index.html')
        except Exception as e:
            return f"Error loading template: {str(e)}", 500

    @app.route('/form', methods=['GET'])
    def form():
        logger.info("form page accessed")
        try:
            return render_template('form.html')
        except Exception as e:
            return f"Error loading template: {str(e)}", 500

    @app.route('/submit', methods=['POST'])
    def submit():
        try:
            # Extract and sanitize form data
            form_data = {
                'name': request.form.get('name', '').strip(),
                'email': request.form.get('email', '').lower().strip(),
                'internship_function': request.form.get('internship_function', '').strip(),
                'telegram_contact': request.form.get('telegram_contact', '').strip(),
                'whatsapp': request.form.get('whatsapp', '').strip()
            }

            # Validate form data
            errors = validate_registration(form_data)
            if errors:
                for error in errors:
                    flash(error, 'danger')
                return redirect(url_for('form'))  # Redirect back to the form with errors

            # Store form data in session
            session['form_data'] = form_data

            # Save student to database
            new_student = Student(
                **form_data,
                payment_status='paid',
                internship_start_date=datetime.utcnow(),
                internship_duration=1  # Default 1 month internship
            )
            
            db.session.add(new_student)
            db.session.commit()

            # Send confirmation email
            send_email(
                new_student.email,
                "Internship Registration Confirmation",
                f"Hello {new_student.name},\n\nYour internship in {new_student.internship_function} has been confirmed!"
            )

            session.pop('form_data', None)
            return redirect(url_for('thank_you'))

        except Exception as e:
            logger.error(f"Unexpected error in /submit: {str(e)}", exc_info=True)
            flash("An unexpected error occurred. Please try again.", 'danger')
            return redirect(url_for('form'))
        # Add other routes (payment callback, thank you, health check) here...

    # Payment Callback Route (Add to register_blueprints)
    @app.route('/payment/callback', methods=['POST'])
    def payment_callback():
        try:
            # Verify payment signature
            params_dict = {
                'razorpay_order_id': request.form['razorpay_order_id'],
                'razorpay_payment_id': request.form['razorpay_payment_id'],
                'razorpay_signature': request.form['razorpay_signature']
            }

            razorpay_client = init_razorpay()
            razorpay_client.utility.verify_payment_signature(params_dict)

            form_data = session.get('form_data')
            if not form_data:
                flash("Session expired. Please register again.", 'danger')
                return redirect(url_for('home'))

            # Save student to database
            new_student = Student(
                **form_data,
                payment_status='paid',
                internship_start_date=datetime.utcnow(),
                internship_duration=1  # Default 1 month internship
            )
            
            db.session.add(new_student)
            db.session.commit()

            # Send confirmation email
            send_email(
                new_student.email,
                "Internship Registration Confirmation",
                f"Hello {new_student.name},\n\nYour internship in {new_student.internship_function} has been confirmed!"
            )

            session.pop('form_data', None)
            return redirect(url_for('thank_you'))

        except IntegrityError:
            db.session.rollback()
            flash("This email is already registered.", 'danger')
            return redirect(url_for('home'))
        except Exception as e:
            logger.error(f"Payment callback error: {str(e)}")
            flash("Payment processing failed. Please contact support.", 'danger')
            return redirect(url_for('home'))

    # Thank You Route
    @app.route('/thank-you')
    def thank_you():
        return render_template('success.html')

# Validation and error handling
def validate_registration(form_data):
    errors = []
    
    # Name validation
    if len(form_data['name']) < 2:
        errors.append("Name must be at least 2 characters")
    
    # Email validation
    if not validate_email(form_data['email']):
        errors.append("Invalid email address")
    
    # Internship function validation
    if len(form_data['internship_function']) < 2:
        errors.append("Internship function is required")
    
    # WhatsApp validation
    if form_data['whatsapp']:
        if not form_data['whatsapp'].isdigit() or len(form_data['whatsapp']) > 15:
            errors.append("Invalid WhatsApp number")
    
    # Telegram validation (optional)
    if form_data['telegram_contact'] and not form_data['telegram_contact'].startswith('@'):
        errors.append("Telegram handle must start with '@'")
    
    return errors

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
            two_months_ago = datetime.utcnow() - timedelta(days=60)
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

# CLI commands
def register_commands(app):
    @app.cli.command('init-db')
    def init_db():
        with app.app_context():
            db.create_all()
            logger.info("Database initialized")

    @app.cli.command('send-test-email')
    def send_test_email():
        try:
            send_email(
                to_email="baliyanvdit@gmail.com",
                subject="Test Email",
                body="This is a test email from the system."
            )
            logger.info("Test email sent successfully")
        except Exception as e:
            logger.error(f"Failed to send test email: {str(e)}")

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
    app = Flask(__name__)
    scheduler = BackgroundScheduler()
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)

    nonce = generate_nonce()
    csp_policy = get_csp_policy(nonce)

    # Initialize Talisman with CSP
    Talisman(
        app,
        content_security_policy=csp_policy,
        content_security_policy_nonce_in=['script-src'],
        force_https=False  # For development
    )
    # Inject nonce into templates
    @app.context_processor
    def inject_nonce():
        return {'csp_nonce': nonce}
    
    # Configure logging
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s [%(request_id)s]: %(message)s'
    )
    for handler in app.logger.handlers + logging.getLogger().handlers:
        handler.setFormatter(formatter)
        handler.addFilter(RequestIdFilter())
    
    # Register blueprints/routes/scheduler
    register_blueprints(app)
    register_commands(app)
    # register_scheduler(sched=scheduler)
    scheduler.add_job(func=print_date_time, trigger="interval", seconds=8000)
    
    
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    app.run(debug=True, use_reloader=False)
