import os
from flask import Flask, request, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import openai
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.units import inch, mm
import os
from PIL import Image as PILImage

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Register Montserrat font
pdfmetrics.registerFont(TTFont('Montserrat', 'static/fonts/Montserrat-Regular.ttf'))
pdfmetrics.registerFont(TTFont('Montserrat-Bold', 'static/fonts/Montserrat-Bold.ttf'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    with open(file_path, 'rb') as file:
        pdf = PdfReader(file)
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

def extract_sections(cv_text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": """You are a CV parser. Extract and format the following sections:

                QUALIFICATIONS section format:
                [Year]
                [Institute]
                [Qualification(s) and Grade(s)]

                WORK HISTORY section format for each role:
                [Company Name]
                [Start Date] - [End Date]
                [Job Title]
                [2-line role summary]
                • [Key responsibility/achievement]
                • [Key responsibility/achievement]
                • [Key responsibility/achievement]
                • [Key responsibility/achievement]
                • [Key responsibility/achievement]

                Format each section exactly as shown above, with line breaks between entries."""},
                {"role": "user", "content": f"Extract and format work history and qualifications from this CV: {cv_text}"}
            ]
        )
        parsed_data = response.choices[0].message.content
        
        # Split into sections
        sections = parsed_data.split('\n\n')
        work_history = []
        qualifications = []
        
        current_section = None
        for section in sections:
            if 'WORK HISTORY' in section.upper():
                current_section = 'work'
                continue
            elif 'QUALIFICATIONS' in section.upper():
                current_section = 'qual'
                continue
            
            if current_section == 'work' and section.strip():
                work_history.append(section.strip())
            elif current_section == 'qual' and section.strip():
                qualifications.append(section.strip())
        
        return work_history, qualifications
    except Exception as e:
        print(f"Error in extract_sections: {e}")
        return [], []

def generate_summary(job_title, cv_text):
    prompt = f"""Create a concise, impactful 100-150 word professional summary for a candidate applying for the role of {job_title}. 
    Requirements:
    1. Write in the third person
    2. Focus on their most relevant experience and key achievements for this role
    3. Highlight their level of expertise and industry knowledge
    4. Be specific and quantifiable where possible
    5. Make it compelling but concise
    
    CV Content: {cv_text}"""
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional CV writer specializing in creating brief, powerful executive summaries that showcase candidates' value proposition."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def resize_logo(logo_path, max_width_mm=100):  
    """Resize the logo while maintaining aspect ratio"""
    with PILImage.open(logo_path) as img:
        # Convert mm to pixels (assuming 300 DPI)
        max_width_px = int(max_width_mm * 300 / 25.4)
        # Calculate height maintaining aspect ratio
        aspect_ratio = img.height / img.width
        new_width = max_width_px
        new_height = int(max_width_px * aspect_ratio)
        
        # Limit maximum height
        max_height_px = int(30 * 300 / 25.4)  
        if new_height > max_height_px:
            new_height = max_height_px
            new_width = int(new_height / aspect_ratio)
        
        # Create resized image
        resized_path = logo_path.replace('.png', '_resized.png')
        img_resized = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)
        img_resized.save(resized_path, 'PNG')
        return resized_path

class LogoDocTemplate(SimpleDocTemplate):
    def __init__(self, filename, logo_path, **kwargs):
        super().__init__(filename, **kwargs)
        self.logo_path = logo_path
        
    def build(self, flowables, **kwargs):
        if self.logo_path and os.path.exists(self.logo_path):
            def header(canvas, doc):
                canvas.saveState()
                try:
                    # Get actual page width in points (1 point = 1/72 inch)
                    page_width = A4[0]  # Width of A4 in points
                    
                    # Set desired width (40% of page width)
                    desired_width = page_width * 0.4
                    
                    # Load the image and get its dimensions
                    img = PILImage.open(self.logo_path)
                    img_width, img_height = img.size
                    aspect_ratio = img_height / img_width
                    
                    # Calculate height maintaining aspect ratio
                    desired_height = desired_width * aspect_ratio
                    
                    # Center horizontally
                    x = (page_width - desired_width) / 2
                    # Position from top (20mm from top)
                    y = A4[1] - (20 * mm) - desired_height
                    
                    # Draw the image
                    canvas.drawImage(self.logo_path, x, y, width=desired_width, height=desired_height)
                except Exception as e:
                    print(f"Error adding logo: {e}")
                canvas.restoreState()
            
            kwargs['onFirstPage'] = header
            kwargs['onLaterPages'] = header
        
        super().build(flowables, **kwargs)

def create_formatted_cv(output_path, candidate_data, summary, qualifications, work_history):
    # Use original logo file directly (no need to resize)
    logo_path = os.path.join(os.getcwd(), 'static', 'images', 'logo.png')
    print(f"Looking for logo at: {logo_path}")
    
    # Create document with logo
    doc = LogoDocTemplate(
        output_path,
        logo_path if os.path.exists(logo_path) else None,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=120,  # Increased top margin to accommodate logo
        bottomMargin=72
    )

    # Define styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='Montserrat',
        fontName='Montserrat',
        fontSize=11,
        leading=14,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='MontserratBold',
        fontName='Montserrat-Bold',
        fontSize=24,
        leading=28,
        spaceAfter=20
    ))
    styles.add(ParagraphStyle(
        name='SectionHeader',
        fontName='Montserrat-Bold',
        fontSize=14,
        leading=18,
        spaceAfter=12,
        spaceBefore=12
    ))
    styles.add(ParagraphStyle(
        name='JobTitle',
        fontName='Montserrat-Bold',
        fontSize=16,
        leading=20,
        spaceAfter=12,
        textColor=colors.HexColor('#444444')
    ))
    styles.add(ParagraphStyle(
        name='CompanyName',
        fontName='Montserrat-Bold',
        fontSize=12,
        leading=15,
        spaceAfter=6
    ))

    # Build document content
    story = []
    
    # Header with candidate name
    story.append(Paragraph(candidate_data['name'], styles['MontserratBold']))
    story.append(Paragraph(candidate_data['job_title'], styles['JobTitle']))
    story.append(Spacer(1, 12))
    
    # Key information
    info_items = {
        'Salary': candidate_data['salary'],
        'Notice Period': candidate_data['notice_period'],
        'Location': candidate_data['location']
    }
    for key, value in info_items.items():
        story.append(Paragraph(f"<b>{key}:</b> {value}", styles['Montserrat']))
    story.append(Spacer(1, 20))
    
    # Executive Summary
    story.append(Paragraph("Professional Summary", styles['SectionHeader']))
    story.append(Paragraph(summary, styles['Montserrat']))
    story.append(Spacer(1, 20))
    
    # Qualifications
    if qualifications:
        story.append(Paragraph("Qualifications", styles['SectionHeader']))
        for qual in qualifications:
            # Split qualification entry into lines
            qual_lines = qual.split('\n')
            for line in qual_lines:
                story.append(Paragraph(line.strip(), styles['Montserrat']))
            story.append(Spacer(1, 12))
    
    # Work History
    if work_history:
        story.append(Paragraph("Professional Experience", styles['SectionHeader']))
        for job in work_history:
            # Split job entry into lines
            job_lines = job.split('\n')
            for i, line in enumerate(job_lines):
                if i == 0:  # Company name
                    story.append(Paragraph(line.strip(), styles['CompanyName']))
                elif line.strip().startswith('•'):  # Bullet points
                    story.append(Paragraph(line.strip(), styles['Montserrat']))
                else:  # Other lines (dates, title, summary)
                    story.append(Paragraph(line.strip(), styles['Montserrat']))
            story.append(Spacer(1, 16))

    doc.build(story)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/cv-formatter')
def cv_formatter():
    return render_template('index.html')

@app.route('/performance-dashboard')
def performance_dashboard():
    return render_template('dashboard.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'cv' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['cv']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Extract text based on file type
        if filename.endswith('.pdf'):
            cv_text = extract_text_from_pdf(filepath)
        else:
            cv_text = extract_text_from_docx(filepath)
        
        # Get form data
        candidate_data = {
            'name': request.form.get('name', 'Unknown'),
            'job_title': request.form.get('job_title'),
            'salary': request.form.get('salary'),
            'notice_period': request.form.get('notice_period'),
            'location': request.form.get('location')
        }
        
        # Generate summary using OpenAI
        summary = generate_summary(candidate_data['job_title'], cv_text)
        
        # Extract work history and qualifications
        work_history, qualifications = extract_sections(cv_text)
        
        # Create formatted CV
        output_filename = f"formatted_{filename.rsplit('.', 1)[0]}.pdf"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        create_formatted_cv(output_path, candidate_data, summary, qualifications, work_history)
        
        return jsonify({
            'success': True,
            'output_file': output_filename
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
