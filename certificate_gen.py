from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def generate_certificate(name, internship):
    # Load the certificate template
    template_path = os.path.join(BASE_DIR, 'certificate_templates/certificate_templates_.jpg')
    output_path = os.path.join(BASE_DIR, 'gen_certificate/generated_certificate.jpg')
    issue_date = datetime.today().strftime("%d-%m-%Y")
    img = Image.open(template_path)
    draw = ImageDraw.Draw(img)

    # Define font (Ensure you have a suitable .ttf font file)
    name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
    date_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    content_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)


    # Define text positions (Adjust based on template)
    name_position = (500, 350)  # X, Y coordinate
    date_position = (350, 805)
    content_position = (899, 443)

    # Add text to image
    draw.text(content_position, internship, fill="black", font=content_font)
    draw.text(name_position, name, fill="black", font=name_font)
    draw.text(date_position, f"{issue_date}", fill="black", font=date_font)

    # Save the certificate
    img.save(output_path)
    print(f"Certificate saved as: {output_path}")


def generate_internship_offer(name, internship):
    """
    Generates an internship offer letter with the given name and internship details.
    
    :param name: The recipient's name
    :param internship: The internship role
    :param template_path: Path to the internship offer template image
    :param output_path: Path to save the generated offer letter
    """
    template_path = os.path.join(BASE_DIR, 'certificate_templates/Internship_Offer_Letter.jpg')
    output_path = os.path.join(BASE_DIR, 'gen_certificate/generated_Internship_Offer_Letter.jpg')
    # Load the template image
    img = Image.open(template_path)
    draw = ImageDraw.Draw(img)
    
    # Define fonts (Ensure the paths to .ttf fonts are correct)
    name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)
    date_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    content_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    
    # Generate issue date
    issue_date = datetime.today().strftime("%d-%m-%Y")
    
    # Define text positions
    date_position = (50, 55)  # Near "Date:" field at the top-left
    name_position = (78, 188)  # Below "Dear" as recipient's name
    internship_position = (278, 222)  # Near internship details
    
    # Add text to image
    draw.text(date_position, f"{issue_date}", fill="black", font=date_font)
    draw.text(name_position, name, fill="black", font=name_font)
    draw.text(internship_position, internship, fill="black", font=content_font)
    
    # Save modified image
    img.save(output_path)
    print(f"Internship offer letter saved at: {output_path}")




if __name__ == "__main__":
    
    # Example usage
    recipient_name = "John Doe"
    internship="Android App Development"

    # generate_certificate(recipient_name, internship)
    # generate_internship_offer(recipient_name,internship)
    print(f"{BASE_DIR}")
# end main