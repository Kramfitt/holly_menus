import os
from app import create_app
from dotenv import load_dotenv

# Load environment variables
if os.path.exists('development.env'):
    load_dotenv('development.env')
    print("\n🔧 Using development environment")
else:
    load_dotenv()
    print("\n🔧 Using default environment")

app = create_app()

if __name__ == "__main__":
    print("\n🚀 Starting Holly Lodge Menu System...")
    
    # Show environment status
    print("\n📝 Environment Configuration:")
    print(f"- FLASK_ENV: {os.getenv('FLASK_ENV', 'production')}")
    print(f"- DEBUG: {os.getenv('FLASK_DEBUG', 'False')}")
    print(f"- SMTP: {os.getenv('SMTP_SERVER', 'Not configured')}")
    
    # Show component status
    print("\n🔍 Component Status:")
    print(f"- Templates Directory: {'✅' if os.path.exists('menu_templates') else '❌'}")
    print(f"- Tesseract OCR: {'✅' if os.path.exists('C:/Program Files/Tesseract-OCR/tesseract.exe') else '❌'}")
    print(f"- Poppler: {'✅' if os.path.exists('C:/Poppler/Release-24.08.0-0/poppler-24.08.0/Library/bin') else '❌'}")
    
    print("\n💻 Server starting at http://localhost:5000\n")
    
    app.run(
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        port=int(os.getenv('PORT', 5000))
    ) 