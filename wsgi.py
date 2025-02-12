print("Loading application...")
from app import create_app

app = create_app()
print("Application loaded successfully!")

if __name__ == '__main__':
    app.run()