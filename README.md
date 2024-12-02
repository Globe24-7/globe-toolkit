# CV Formatter

A professional CV formatting tool that processes candidate CVs and generates standardized, branded documents.

## Features

- Upload PDF or Word document CVs
- AI-powered CV parsing and summary generation
- Professional formatting with company branding
- Standardized output format for all CVs
- Web-based interface for easy access

## Setup

1. Install Python 3.8 or higher
2. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Set up your OpenAI API key in `.env`:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```
4. Place your company logo in `static/images/logo.png`

## Running the Application

1. Navigate to the project directory:
   ```bash
   cd path/to/cv_processor
   ```
2. Start the Flask server:
   ```bash
   python app.py
   ```
3. Open your browser and go to:
   ```
   http://127.0.0.1:5000
   ```

## Usage

1. Enter candidate details:
   - Name
   - Job Title
   - Salary
   - Notice Period
   - Location
2. Upload the candidate's CV (PDF or Word format)
3. Click "Process CV"
4. The formatted CV will be automatically downloaded

## File Structure

```
cv_processor/
├── app.py              # Main application file
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (API keys)
├── static/
│   ├── images/        # Logo and other images
│   └── fonts/         # Font files
├── templates/
│   └── index.html     # Web interface template
└── uploads/           # Temporary storage for uploads
```

## Dependencies

- Flask
- python-docx
- PyPDF2
- reportlab
- openai
- python-dotenv
- Pillow
- Werkzeug
- gunicorn
