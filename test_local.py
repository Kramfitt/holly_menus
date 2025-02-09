from menu_scheduler import load_config, send_test_email

def main():
    try:
        print("Loading config...")
        config = load_config()
        
        print("Sending test email...")
        send_test_email(config)
        
        print("Test completed!")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 