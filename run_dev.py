import os
from app import app
from dotenv import load_dotenv

# Load development environment
if os.path.exists('development.env'):
    load_dotenv('development.env')
else:
    print("⚠️ development.env not found, using default settings")

if __name__ == "__main__":
    print("\n🚀 Starting development server...")
    print("\n📝 Environment:")
    print(f"- FLASK_ENV: {os.getenv('FLASK_ENV')}")
    print(f"- DEBUG: {os.getenv('DEBUG')}")
    print(f"- SUPABASE: {'Connected' if os.getenv('SUPABASE_URL') else 'Missing credentials'}")
    print(f"- SMTP: {os.getenv('SMTP_SERVER', 'Not configured')}")
    
    app.run(debug=True, port=5000) 