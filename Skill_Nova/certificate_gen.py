from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

def generate_certificate(template_path, output_path, name, date):
    # Load the certificate template
    img = Image.open(template_path)
    draw = ImageDraw.Draw(img)

    # Define font (Ensure you have a suitable .ttf font file)
    name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
    date_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 35)
    content_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 35)

    text=f"""

        This certificate is proudly presented to {name}
        In recognition of your dedication, hard work, and outstanding performance during the 
        [Internship/Training Program] at Oasis Infobyte.
        Your commitment to learning and excellence has been truly commendable. 
        We appreciate your contributions and wish you continued success in all your future endeavors.
        """

    # Define text positions (Adjust based on template)
    name_position = (850, 600)  # X, Y coordinate
    date_position = (550, 1260)
    content_position = (100, 650)

    # Add text to image
    draw.text(content_position, text, fill="black", font=content_font)
    draw.text(name_position, name, fill="black", font=name_font)
    draw.text(date_position, f"{date}", fill="black", font=date_font)

    # Save the certificate
    img.save(output_path)
    print(f"Certificate saved as: {output_path}")



def generate_certificate_2(template_path, output_path, name, date):
    # Load the certificate template
    img = Image.open(template_path)
    draw = ImageDraw.Draw(img)

    # Define font (Ensure you have a suitable .ttf font file)
    name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
    date_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    content_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)

    text="Web Dev"

    # Define text positions (Adjust based on template)
    name_position = (500, 350)  # X, Y coordinate
    date_position = (350, 805)
    content_position = (742, 453)

    # Add text to image
    draw.text(content_position, text, fill="black", font=content_font)
    draw.text(name_position, name, fill="black", font=name_font)
    draw.text(date_position, f"{date}", fill="black", font=date_font)

    # Save the certificate
    img.save(output_path)
    print(f"Certificate saved as: {output_path}")


# Example usage
template_path = "/home/udit/Documents/Github/002_Skill_Nova/Skill_Nova/certificate_templates/photo_2025-02-12_07-16-05.jpg"
output_path = "/home/udit/Documents/Github/002_Skill_Nova/Skill_Nova/gen_certificate/generated_certificate.png"
recipient_name = "John Doe"
issue_date = datetime.today().strftime("%d-%m-%Y")

generate_certificate_2(template_path, output_path, recipient_name, issue_date)
