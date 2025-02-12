import smtplib
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

def test_connection():
    try:
        # Get credentials from .env
        username = 'ashvillenz@gmail.com' #os.getenv('SMTP_USERNAME')
        password = 'ktrf xmyb zcku jayt'#os.getenv('SMTP_PASSWORD')
        
        print(f"Testing connection for: {username}")
        
        # Try to connect
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        
        # Try to login
        server.login(username, password)
        print("Success! Connection and login worked!")
        
        # Close connection
        server.quit()
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_connection() 