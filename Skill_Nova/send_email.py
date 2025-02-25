from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def send_email(subject, body,to_email="baliyanvdit@gmail.com",attachment_path=None):
    try:
        sender_email = "contact.skillnova@gmail.com"
        password = "sdwn temk livb fxkf"

        if not sender_email or not password:
            raise ValueError("Missing email credentials")

        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # (Optional) If you want to attach a PDF or other file
        if attachment_path and os.path.isfile(attachment_path):
            with open(attachment_path, "rb") as f:
                file_data = f.read()
            attachment = MIMEText(file_data, "base64", _charset="utf-8")
            attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
            message.attach(attachment)

        with smtplib.SMTP(os.getenv("SMTP_SERVER", "smtp.gmail.com"), 
             int(os.getenv("SMTP_PORT", 587))) as server:
            server.starttls()
            server.login(sender_email, password)
            server.send_message(message)
        print(f"Email sent to {to_email}")

    except Exception as e:
        print(f"Email failed to {to_email}: {str(e)}")
        raise



pdf_path_dir={"Web Development":"",
              "Android App Development":"",
              "Data Science":"",
              "Java Programming":"",
              "Python Programming":"",
              "C++ Programming":"",
              "UI/UX Design":"",
              "Artificial Intelligence":"ai.pdf",
              "Machine Learning":""}


internship=pdf_path_dir["Artificial Intelligence"]
pdf_path = os.path.join(BASE_DIR, 'Task_pdf',internship)

send_email(subject="hehehe!!!!!", body="---------------",to_email="baliyanvdit@gmail.com",attachment_path=pdf_path)