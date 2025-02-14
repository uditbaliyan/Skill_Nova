from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib



def send_email(id):
    receiver_email = "healthmonitoring00@gmail.com"

    # Email configuration
    sender_email = "contact.skillnova@gmail.com"
    password = "sdwn temk livb fxkf"  # Use environment variables for security
    subject = "Health Monitoring System Alert"

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    body = "What's up.\n"
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        print("Email sent successfully!")
        return "Function invoked successfully"
    except Exception as e:
        print(f"Error sending email: {e}")
        return "Failed to send email.", 500

