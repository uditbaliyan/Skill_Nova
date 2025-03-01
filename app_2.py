import os
import logging
import atexit
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import razorpay
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from certificate_gen import generate_internship_offer,generate_certificate



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
# Initialize SQLAlchemy globally
# ------------------------------------------------------------------------------
db = SQLAlchemy()

# ------------------------------------------------------------------------------
# Configuration class
# ------------------------------------------------------------------------------
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret")
    
    # APScheduler config
    SCHEDULER_API_ENABLED = False
    SCHEDULER_JOB_DEFAULTS = {'coalesce': True, 'max_instances': 1}
    SCHEDULER_ENABLED = True
    
    # Database
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance/students.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=15)
    
    # Razorpay credentials
    RAZORPAY_KEY = os.getenv("RAZORPAY_KEY")
    RAZORPAY_SECRET = os.getenv("RAZORPAY_SECRET")

# ------------------------------------------------------------------------------
# Database model
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
    completion_email_sent = db.Column(db.Boolean, default=False)
    # Tracks if internship details email was sent loi
    internship_details_email_sent = db.Column(db.Boolean, default=False)
    internship_loi_email_sent = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Student {self.email}>'

# ------------------------------------------------------------------------------
# Create and configure Flask app via factory
# ------------------------------------------------------------------------------
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize SQLAlchemy with this app
    db.init_app(app)

    # Initialize Razorpay client
    client = razorpay.Client(auth=(app.config["RAZORPAY_KEY"], app.config["RAZORPAY_SECRET"]))

    # --------------------------------------------------------------------------
    # Routes
    # --------------------------------------------------------------------------
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
        """
        Handles the form submission and payment verification from the frontend.
        Expects JSON data with:
          - razorpay_payment_id
          - razorpay_order_id
          - razorpay_signature
          - name, email, domain, whatsapp, telegram_contact
        """
        try:
            data = request.json
            if not data:
                return jsonify({"status": "error", "message": "No data received"}), 400

            payment_id = data.get("razorpay_payment_id")
            order_id = data.get("razorpay_order_id")
            signature = data.get("razorpay_signature")
            name = data.get("name")
            email = data.get("email")
            internship_function = data.get("domain")

            # (Optional) Validate payment signature in production:
            # params = {
            #     'razorpay_order_id': order_id,
            #     'razorpay_payment_id': payment_id,
            #     'razorpay_signature': signature
            # }
            # try:
            #     client.utility.verify_payment_signature(params)
            # except razorpay.errors.SignatureVerificationError:
            #     return jsonify({"status": "error", "message": "Invalid payment signature"}), 400

            form_data = {
                "name": name,
                "email": email,
                "internship_function": internship_function,
                "whatsapp": data.get("whatsapp"),
                "telegram_contact": data.get("telegram_contact"),
                "payment_id": payment_id,
                "payment_status": "paid",
                "internship_start_date": datetime.utcnow(),
                "internship_duration": 1  # Example: 1 month
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
                        raise e

            # Immediately send a confirmation email
            send_confirmation_email(email, name, internship_function)

            # Clear session data if used
            session.pop('form_data', None)
            session.pop('razorpay_order_id', None)

            return jsonify({"status": "success", "redirect_url": "/thank-you"})

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error processing payment/registration: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/payment-failed', methods=['POST'])
    def payment_failed():
        """
        Logs payment failures from the frontend or Razorpay webhook.
        """
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

    # --------------------------------------------------------------------------
    # Error Handlers
    # --------------------------------------------------------------------------
    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        return render_template('500.html'), 500

    # --------------------------------------------------------------------------
    # Database Initialization
    # --------------------------------------------------------------------------
    with app.app_context():
        db.create_all()
        logger.info("Database tables created or verified")

    return app

# ------------------------------------------------------------------------------
# APScheduler Task: Send Internship Details After 24 Hours
# ------------------------------------------------------------------------------
def send_internship_details_if_due():
    """
    Runs periodically (e.g., every hour) to check if 24 hours have passed
    since the student started the internship. If yes and the internship
    details email hasn't been sent, send it now.
    """
    with app.app_context():
        try:
            now = datetime.now()
            # Filter students who are paid, haven't received the details email yet
            students = Student.query.filter_by(
                payment_status='paid',
                internship_details_email_sent=False
            ).all()

            for student in students:
                # Check if 24 hours have passed hours=4
                if student.internship_start_date:
                    due_time = student.internship_start_date + timedelta(seconds=40)
                    if now >= due_time:
                        # Send the internship details email
                        send_internship_details_email(
                            student.email,
                            student.name,
                            student.internship_function
                        )
                        # Mark as sent
                        student.internship_details_email_sent = True
                        db.session.commit()

        except Exception as e:
            logger.error(f"Error in send_internship_details_if_due: {str(e)}")


def send_internship_loi_if_due():
    """
    Runs periodically (e.g., every hour) to check if 24 hours have passed
    since the student started the internship. If yes and the internship
    details email hasn't been sent, send it now.
    """
    with app.app_context():
        try:
            now = datetime.now()
            # Filter students who are paid, haven't received the details email yet
            students = Student.query.filter_by(
                payment_status='paid',
                internship_loi_email_sent=False
            ).all()

            for student in students:
                # Check if 24 hours have passed hours=4
                if student.internship_start_date:
                    due_time = student.internship_start_date + timedelta(seconds=40)
                    if now >= due_time:
                        # Send the internship details email
                        send_internship_details_email(
                            student.email,
                            student.name,
                            student.internship_function
                        )
                        # Mark as sent
                        student.internship_details_email_sent = True
                        db.session.commit()

        except Exception as e:
            logger.error(f"Error in send_internship_details_if_due: {str(e)}")



# ------------------------------------------------------------------------------
# Scheduled Tasks 
# ------------------------------------------------------------------------------
def send_weekly_emails():
    with app.app_context():
        try:
            students = Student.query.filter_by(payment_status="paid").all()
            for student in students:
                subject = "Weekly Internship Update"
                body = f"Hi {student.name},\n\nHere are your tasks for this week..."
                send_email(student.email, subject, body)
        except Exception as e:
            logger.error(f"Error in send_weekly_emails: {str(e)}")

def send_completion_emails():
    with app.app_context():
        try:
            now = datetime.now()
            students = Student.query.filter_by(payment_status='paid', completion_email_sent=False).all()
            for student in students:
                if student.internship_start_date:
                    end_date = student.internship_start_date + timedelta(days=30 * student.internship_duration)
                    if now >= end_date:
                        subject = "Internship Completion Certificate"
                        body = f"Congratulations {student.name}!\n\nYou've successfully completed your internship."
                        generate_certificate(name=student.name,internship=student.internship_function)
                        send_email(student.email, subject, body,attachment_paths=["/home/udit/Documents/Github/002_Skill_Nova/Skill_Nova/gen_certificate/generated_certificate.png"])
                        student.completion_email_sent = True
                        db.session.commit()
        except Exception as e:
            logger.error(f"Completion emails failed: {str(e)}")

def cleanup_old_entries():
    with app.app_context():
        try:
            two_months_ago = datetime.now(timezone.utc) - timedelta(days=60)
            old_students = Student.query.filter(Student.created_at < two_months_ago).all()
            for student in old_students:
                db.session.delete(student)
            db.session.commit()
            logger.info("Old student entries have been cleaned up.")
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
            db.session.rollback()






def send_email(to_email, subject, body, attachment_paths=None):
    """
    Sends an email using SMTP credentials stored in .env.
    Optionally attach a PDF or any file if attachment_path is provided.
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

        # Attach files if provided
        if attachment_paths:
            for attachment_path in attachment_paths:
                if attachment_path and os.path.isfile(attachment_path):
                    with open(attachment_path, "rb") as f:
                        file_data = f.read()
                    attachment = MIMEText(file_data, "base64", _charset="utf-8")
                    attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                    message.attach(attachment)

        # Send via SMTP
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, password)
            server.send_message(message)

        logger.info(f"Email sent to {to_email}")

    except Exception as e:
        logger.error(f"Email failed to {to_email}: {str(e)}")
        raise



def send_confirmation_email(email, name, internship_function):
    """
    Sends a simple registration confirmation email immediately.
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
    This function sends the detailed internship email **24 hours** after registration.
    RQ enqueues this function and runs it in a separate worker process.
    """
    pdf_path_dir={"Web Development":"web-dev.pdf",
              "Android App Development":"",
              "Data Science":"data-science.pdf",
              "Java Programming":"java-prog.pdf",
              "Python Programming":"Python.pdf",
              "C++ Programming":"c++prog.pdf",
              "UI/UX Design":"ui-ux.pdf",
              "Artificial Intelligence":"ai.pdf",
              "Machine Learning":"ML.pdf"}
    
    subject = "SkillNova Virtual Internship - Detailed Instructions"
    body = f"""Dear {name},

        Congratulations! 🎉 Your registration for the SkillNova Virtual Internship Program has been successfully confirmed. We are excited to have you on board and look forward to helping you gain hands-on experience in your chosen domain.

        Internship Details:
        ✅ Internship Mode: 100% Virtual
        ✅ Duration: 4 Week
        ✅ Domain: {internship_function}
        ✅ Work Structure: Weekly Assignments & Real-World Projects
        ✅ Guidance & Mentorship: Support from industry professionals
        ✅ Certificate of Completion: Upon successful completion of the program

        Your Learning Experience:
        During this internship, you will:
        🔹 Work on structured assignments tailored to {internship_function}
        🔹 Gain hands-on experience with real-world projects
        🔹 Develop industry-relevant skills to enhance your career prospects
        🔹 Receive guidance from experienced mentors

        Project & Assignment Details:
        Attached to this email, you will find a PDF containing details of the projects and assignments you will be working on during the internship.

        📌 Weekly Tasks:
        Every week, you will receive a new assignment along with project submission links.
        Assignments and projects must be completed within the given deadlines.
        Submission links will be shared with you via email on a weekly basis.

        Please download and review the attached project document carefully. 
        If you have any queries, feel free to reach out to us at contact.skillnova@gmail.com or reply to this email.

        We look forward to seeing you grow and succeed in this program! 🚀

        Best Regards,
        SkillNova Team
        www.skillnovatech.in
        contact.skillnova@gmail.com
        """
    # If you have a PDF or other attachment:
    internship=pdf_path_dir[internship_function]
    pdf_path = os.path.join(Config.BASE_DIR, 'Task_pdf',internship)
    # pdf_path = None

    print(f"{pdf_path}")
    send_email(
        to_email=email,
        subject=subject,
        body=body,
        attachment_paths=pdf_path
    )


def send_internship_loi_email(email, name, internship_function):
    """
    This function sends the detailed internship email **24 hours** after registration.
    RQ enqueues this function and runs it in a separate worker process.
    """
    
    subject = "SkillNova Virtual Internship - Detailed Instructions"
    body = f"""Dear {name},

        Congratulations! 🎉 Your registration for the SkillNova Virtual Internship Program has been successfully confirmed. We are excited to have you on board and look forward to helping you gain hands-on experience in your chosen domain.

        Internship Details:
        ✅ Internship Mode: 100% Virtual
        ✅ Duration: 4 Week
        ✅ Domain: {internship_function}
        ✅ Work Structure: Weekly Assignments & Real-World Projects
        ✅ Guidance & Mentorship: Support from industry professionals
        ✅ Certificate of Completion: Upon successful completion of the program

        Your Learning Experience:
        During this internship, you will:
        🔹 Work on structured assignments tailored to {internship_function}
        🔹 Gain hands-on experience with real-world projects
        🔹 Develop industry-relevant skills to enhance your career prospects
        🔹 Receive guidance from experienced mentors

        Project & Assignment Details:
        Attached to this email, you will find a PDF containing details of the projects and assignments you will be working on during the internship.

        📌 Weekly Tasks:
        Every week, you will receive a new assignment along with project submission links.
        Assignments and projects must be completed within the given deadlines.
        Submission links will be shared with you via email on a weekly basis.

        Please download and review the attached project document carefully. 
        If you have any queries, feel free to reach out to us at contact.skillnova@gmail.com or reply to this email.

        We look forward to seeing you grow and succeed in this program! 🚀

        Best Regards,
        SkillNova Team
        www.skillnovatech.in
        contact.skillnova@gmail.com
        """
    generate_internship_offer(name=name,internship=internship_function)
    send_email(
        to_email=email,
        subject=subject,
        body=body,
        attachment_paths="/home/udit/Documents/Github/002_Skill_Nova/Skill_Nova/gen_certificate/generated_Internship_Offer_Letter.png"
    )


# ------------------------------------------------------------------------------
# Main Entry Point
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    app = create_app()

    scheduler = BackgroundScheduler()
    if app.config["SCHEDULER_ENABLED"]:
        # Check for internship details email every hour
        scheduler.add_job(
            id='send_internship_details_if_due',
            func=send_internship_details_if_due,
            trigger='interval',
            seconds=60
        )
        scheduler.add_job(
            id='send_internship_loi_if_due',
            func=send_internship_loi_if_due,
            trigger='interval',
            seconds=60
        )
            # trigger='cron',
            # hour=10
        # Additional tasks
        scheduler.add_job(
            id='weekly_emails',
            func=send_weekly_emails,
            trigger='interval',
            seconds=70
        )
        #             trigger='cron',
        #     day_of_week='mon',
        #     hour=9
        scheduler.add_job(
            id='cleanup',
            func=cleanup_old_entries,
            trigger='interval',
            seconds=80
        )
        # trigger='cron',
        #     day=1,
        #     hour=0
        scheduler.add_job(
            id='completion_emails',
            func=send_completion_emails,
            trigger='interval',
            seconds=80
        )
        # trigger='cron',
        #     hour=10,
        #     minute=0
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())

    # Run the Flask dev server
    app.run(debug=True, use_reloader=False)
