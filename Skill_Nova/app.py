from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import razorpay
from razorpay.errors import BadRequestError, ServerError
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
import logging
import uuid
from dotenv import load_dotenv
import validators
import html

# Load environment variables
load_dotenv()

# Configuration class
class Config:
    SCHEDULER_API_ENABLED = True
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(os.path.abspath(os.path.dirname(__file__)), 'students.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=15)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s [%(request_id)s]: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = session.get('request_id', 'no-request-id')
        return True

logging.getLogger().addFilter(RequestIdFilter())

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(32))

# Security headers
Talisman(app, content_security_policy={
    'default-src': "'self'",
    'script-src': ["'self'", "https://checkout.razorpay.com"],
    'style-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", "data:"]
})

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Database initialization
db = SQLAlchemy(app)

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

    def __repr__(self):
        return f'<Student {self.email}>'

# Initialize Razorpay client
try:
    razorpay_client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY"), os.getenv("RAZORPAY_SECRET")))
except Exception as e:
    logger.error(f"Failed to initialize Razorpay client: {str(e)}", extra={'request_id': 'system-init'})
    raise

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# Error handlers
@app.errorhandler(400)
def bad_request(e):
    return render_template('error.html',
                         error_code=400,
                         message="Invalid request"), 400

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html',
                         error_code=404,
                         message="Page not found"), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template('error.html',
                         error_code=429,
                         message="Too many requests. Please try again later."), 429

@app.errorhandler(500)
def internal_server_error(e):
    request_id = session.get('request_id', str(uuid.uuid4()))
    logger.error(f"Internal server error (Request ID: {request_id}): {str(e)}")
    return render_template('error.html',
                         error_code=500,
                         message=f"Internal server error (Request ID: {request_id})"), 500

@app.before_request
def set_request_id():
    if 'request_id' not in session:
        session['request_id'] = str(uuid.uuid4())
    session.modified = True

def validate_registration_form(form):
    """Validate and sanitize form input data"""
    errors = []
    sanitized = {}
    
    # Sanitize and validate name
    name = html.escape(form.get('name', '').strip())
    if len(name) < 2:
        errors.append("Name must be at least 2 characters")
    else:
        sanitized['name'] = name
    
    # Validate and sanitize email
    email = form.get('email', '').lower().strip()
    if not validators.email(email):
        errors.append("Invalid email address")
    else:
        sanitized['email'] = email
    
    # Validate internship function
    internship_function = html.escape(form.get('internship_function', '').strip())
    if len(internship_function) < 2:
        errors.append("Internship function is required")
    else:
        sanitized['internship_function'] = internship_function
    
    # Validate contact info
    telegram_contact = html.escape(form.get('telegram_contact', '').strip())
    sanitized['telegram_contact'] = telegram_contact
    
    whatsapp = form.get('whatsapp', '').strip()
    if whatsapp and (not whatsapp.isdigit() or len(whatsapp) > 15):
        errors.append("Invalid WhatsApp number")
    else:
        sanitized['whatsapp'] = whatsapp
    
    return errors, sanitized

@app.route('/', methods=['GET'])
@limiter.limit("10 per minute")
def home():
    logger.info("Home page accessed", extra={'request_id': session['request_id']})
    return render_template('form.html')

@app.route('/submit', methods=['POST'])
@limiter.limit("5 per minute")
def submit():
    try:
        errors, sanitized_data = validate_registration_form(request.form)
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('home'))

        session['form_data'] = sanitized_data
        
        try:
            razorpay_order = razorpay_client.order.create({
                'amount': 50000,
                'currency': 'INR',
                'receipt': f"receipt_{datetime.now().timestamp()}"
            })
            logger.info(f"Razorpay order created: {razorpay_order['id']}", 
                       extra={'request_id': session['request_id']})
            
        except (BadRequestError, ServerError) as e:
            logger.error(f"Razorpay order creation failed: {str(e)}", 
                        extra={'request_id': session['request_id']})
            flash("Payment gateway error. Please try again later.", 'danger')
            return redirect(url_for('home'))

        return render_template('payment.html',
                            order=razorpay_order,
                            key=os.getenv("RAZORPAY_KEY"),
                            request_id=session['request_id'])

    except Exception as e:
        logger.error(f"Form submission error: {str(e)}", 
                    extra={'request_id': session['request_id']})
        flash("An unexpected error occurred. Please try again.", 'danger')
        return redirect(url_for('home'))

@app.route('/payment/callback', methods=['POST'])
@limiter.limit("10 per minute")
def payment_callback():
    try:
        # Verify payment signature
        params_dict = {
            'razorpay_order_id': request.form['razorpay_order_id'],
            'razorpay_payment_id': request.form['razorpay_payment_id'],
            'razorpay_signature': request.form['razorpay_signature']
        }

        try:
            razorpay_client.utility.verify_payment_signature(params_dict)
            logger.info(f"Payment verified: {params_dict['razorpay_payment_id']}",
                       extra={'request_id': session['request_id']})
        except razorpay.errors.SignatureVerificationError as e:
            logger.warning(f"Invalid payment signature: {str(e)}", 
                          extra={'request_id': session['request_id']})
            flash("Payment verification failed. Please contact support.", 'danger')
            return redirect(url_for('home'))

        form_data = session.get('form_data')
        if not form_data:
            logger.warning("Missing form data in session", 
                          extra={'request_id': session['request_id']})
            flash("Session expired. Please register again.", 'danger')
            return redirect(url_for('home'))

        try:
            new_student = Student(
                **form_data,
                payment_status='paid'
            )
            db.session.add(new_student)
            db.session.commit()
            logger.info(f"New student registered: {new_student.email}", 
                       extra={'request_id': session['request_id']})
            
        except IntegrityError:
            db.session.rollback()
            logger.warning(f"Duplicate registration attempt: {form_data['email']}", 
                          extra={'request_id': session['request_id']})
            flash("This email is already registered.", 'danger')
            return redirect(url_for('home'))
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error: {str(e)}", 
                        extra={'request_id': session['request_id']})
            flash("Registration failed. Please contact support.", 'danger')
            return redirect(url_for('home'))

        try:
            send_email(
                to_email=new_student.email,
                subject="Welcome to Our Internship Program!",
                body=f"Hi {new_student.name},\n\nThank you for joining our internship program!"
            )
            logger.info(f"Onboarding email sent to {new_student.email}", 
                       extra={'request_id': session['request_id']})
        except Exception as e:
            logger.error(f"Failed to send onboarding email: {str(e)}", 
                        extra={'request_id': session['request_id']})

        session.pop('form_data', None)
        return redirect(url_for('thank_you'))

    except Exception as e:
        logger.error(f"Payment callback error: {str(e)}", 
                    extra={'request_id': session['request_id']})
        flash("Payment processing failed. Please contact support.", 'danger')
        return redirect(url_for('home'))

def send_email(to_email, subject, body, attachments=None):
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

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(sender_email, password)
            server.send_message(message)
        logger.info(f"Email sent to {to_email}")

    except Exception as e:
        logger.error(f"Email failed to {to_email}: {str(e)}")
        raise

# Scheduled tasks with connection cleanup
def send_weekly_emails():
    try:
        students = Student.query.filter_by(payment_status="paid").all()
        for student in students:
            try:
                with app.app_context():
                    send_email(
                        to_email=student.email,
                        subject="Weekly Internship Update",
                        body=f"Hi {student.name},\n\nHere are your tasks for this week..."
                    )
            except Exception as e:
                logger.error(f"Failed to send weekly email to {student.email}: {str(e)}")
    except Exception as e:
        logger.error(f"Weekly emails task failed: {str(e)}")
    finally:
        db.session.remove()

def cleanup_old_entries():
    try:
        three_months_ago = datetime.utcnow() - timedelta(days=90)
        old_students = Student.query.filter(Student.created_at < three_months_ago).all()
        
        for student in old_students:
            try:
                db.session.delete(student)
            except Exception as e:
                logger.error(f"Failed to delete student {student.id}: {str(e)}")
                db.session.rollback()
        db.session.commit()
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        db.session.rollback()
    finally:
        db.session.remove()

# Scheduler setup
scheduler = APScheduler()
if not app.debug:
    scheduler.add_job(
        id='weekly_emails',
        func=send_weekly_emails,
        trigger='cron',
        day_of_week='mon',
        hour=9
    )
    scheduler.add_job(
        id='cleanup',
        func=cleanup_old_entries,
        trigger='cron',
        day=1,
        hour=0
    )
    try:
        scheduler.init_app(app)
        scheduler.start()
    except Exception as e:
        logger.error(f"Scheduler failed to start: {str(e)}")
        raise

@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')

@app.route('/health')
def health_check():
    try:
        db.session.execute("SELECT 1")
        return "OK", 200
    except SQLAlchemyError:
        return "Database connection failed", 500

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            raise
    app.run(debug=os.getenv("FLASK_DEBUG", False))