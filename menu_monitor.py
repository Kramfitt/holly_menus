import os
import imaplib
import email
import tempfile
import shutil
from email.header import decode_header
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
import logging
from ProcessToImage import convert_pdf_to_images, correct_orientation
from menu_scheduler import load_config
from menu_utils import add_dates_to_menu
import re
import pytesseract
from PIL import Image
import cv2
import numpy as np
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('menu_monitor.log')
    ]
)
logger = logging.getLogger(__name__)

class MenuEmailMonitor:
    def __init__(self):
        self.config = load_config()
        self.imap_server = self.config['email'].get('imap_server', 'imap.gmail.com')
        self.email = os.getenv('SMTP_USERNAME')
        self.password = os.getenv('SMTP_PASSWORD')
        self.poppler_path = "C:\\Poppler\\Release-24.08.0-0\\poppler-24.08.0\\Library\\bin"
        
        # Create directories if they don't exist
        self.temp_dir = 'temp_images'
        self.templates_dir = 'menu_templates'
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.templates_dir, exist_ok=True)
        os.makedirs('output_images', exist_ok=True)
        os.makedirs('temp_menus', exist_ok=True)
        
        # Set up dedicated temp directory
        os.makedirs(os.path.join(tempfile.gettempdir(), 'menu_system'), exist_ok=True)
        tempfile.tempdir = os.path.join(tempfile.gettempdir(), 'menu_system')
        
        logger.info(f"Initialized MenuEmailMonitor with email: {self.email}")
        logger.info(f"Templates directory: {os.path.abspath(self.templates_dir)}")
        
        # Initial cleanup of old files
        self.cleanup_old_files()
        
        # Ensure we have our Menus folder
        self.ensure_folders()

    def ensure_folders(self):
        """Ensure Menus folder exists"""
        try:
            mail = self.connect()
            
            # List all folders
            _, folders = mail.list()
            folder_names = [f.decode().split('"/"')[-1].strip() for f in folders]
            
            # Create Menus folder if it doesn't exist
            menus_folder = '"Menus"'
            if menus_folder not in folder_names:
                mail.create('Menus')
                logger.info("Created 'Menus' folder")
            
            mail.logout()
        except Exception as e:
            logger.error(f"Error ensuring Menus folder exists: {e}")

    def is_email_processed(self, mail: imaplib.IMAP4_SSL, message_id: str) -> bool:
        """Check if an email has already been processed (marked as read)"""
        # We don't need to check - we only get UNSEEN messages in process_new_emails
        return False

    def mark_as_processed(self, mail: imaplib.IMAP4_SSL, msg_num: bytes, message_id: str):
        """Mark email as processed by setting the Seen flag"""
        try:
            # Mark as read
            mail.store(msg_num, '+FLAGS', '\\Seen')
            logger.info(f"Marked email {message_id} as read in Menus folder")
        except Exception as e:
            logger.error(f"Error marking email as processed: {e}")

    def cleanup_old_files(self, max_age_hours: int = 24):
        """Clean up temporary files older than specified hours"""
        try:
            now = datetime.now()
            total_count = 0
            
            # Directories to clean
            temp_dirs = [
                self.temp_dir,  # temp_images
                'output_images',  # processed outputs
                'temp_menus',    # temporary menu files
                os.path.join(tempfile.gettempdir(), 'menu_system')  # system temp files
            ]
            
            # Create a dedicated temp directory for our system
            os.makedirs(os.path.join(tempfile.gettempdir(), 'menu_system'), exist_ok=True)
            
            for temp_dir in temp_dirs:
                if not os.path.exists(temp_dir):
                    continue
                    
                dir_count = 0
                logger.info(f"Cleaning directory: {temp_dir}")
                
                try:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                # Get file stats
                                stats = os.stat(file_path)
                                file_time = datetime.fromtimestamp(stats.st_mtime)  # Use modification time
                                
                                # Check if file is too old
                                if now - file_time > timedelta(hours=max_age_hours):
                                    try:
                                        os.remove(file_path)
                                        dir_count += 1
                                    except PermissionError:
                                        logger.warning(f"Could not delete file (in use): {file_path}")
                                    except FileNotFoundError:
                                        # File was already deleted
                                        pass
                                    
                            except (OSError, FileNotFoundError) as e:
                                logger.warning(f"Error checking file {file_path}: {e}")
                                continue
                        
                        # Remove empty directories
                        for dir in dirs:
                            dir_path = os.path.join(root, dir)
                            try:
                                if not os.listdir(dir_path):  # if directory is empty
                                    os.rmdir(dir_path)
                                    logger.info(f"Removed empty directory: {dir_path}")
                            except (OSError, FileNotFoundError) as e:
                                logger.warning(f"Error removing directory {dir_path}: {e}")
                    
                    if dir_count > 0:
                        logger.info(f"Cleaned up {dir_count} files from {temp_dir}")
                        total_count += dir_count
                        
                except Exception as e:
                    logger.error(f"Error cleaning directory {temp_dir}: {e}")
                    continue
            
            if total_count > 0:
                logger.info(f"Total files cleaned up: {total_count}")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def connect(self) -> imaplib.IMAP4_SSL:
        """Connect to the IMAP server"""
        try:
            logger.info("Connecting to IMAP server...")
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email, self.password)
            logger.info("Successfully connected to IMAP server")
            return mail
        except Exception as e:
            logger.error(f"Failed to connect to IMAP server: {e}")
            raise

    def extract_dates_from_image(self, image_path: str) -> Optional[Dict[str, str]]:
        """
        Extract dates from the menu header using OCR.
        Returns a dictionary mapping day names to dates.
        """
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to read image: {image_path}")
                return None

            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Crop to just the header area (approximately top 15% of image)
            height = gray.shape[0]
            header = gray[0:int(height * 0.15), :]

            # Threshold to get black text
            _, binary = cv2.threshold(header, 200, 255, cv2.THRESH_BINARY)

            # Convert to PIL Image for Tesseract
            pil_image = Image.fromarray(binary)

            # Extract text
            text = pytesseract.image_to_string(pil_image)
            
            # Define regex pattern for dates
            # Matches patterns like "Mon 3rd March", "Tue 4th March", etc.
            date_pattern = r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d+(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December))'
            
            # Find all matches
            matches = re.findall(date_pattern, text)
            
            if not matches:
                logger.warning("No dates found in header")
                return None

            # Create dictionary of day -> date
            dates = {}
            for day, date in matches:
                dates[day] = date.strip()

            logger.info(f"Extracted dates: {dates}")
            return dates

        except Exception as e:
            logger.error(f"Error extracting dates: {e}")
            return None

    def combine_with_master_menu(self, dates: Dict[str, str], master_menu_path: str) -> str:
        """
        Combine extracted dates with the master menu template.
        Returns path to the new combined PDF.
        """
        try:
            # Create output path
            output_path = os.path.join(
                'temp_menus', 
                f'combined_menu_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            )
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Add dates to the master menu
            success = add_dates_to_menu(master_menu_path, dates, output_path)
            
            if success:
                logger.info(f"Successfully created combined menu: {output_path}")
                return output_path
            else:
                logger.error("Failed to create combined menu")
                return None

        except Exception as e:
            logger.error(f"Error combining menus: {e}")
            return None

    def extract_week_number(self, text: str) -> Optional[int]:
        """Extract week number from text"""
        try:
            # Look for patterns like "Week 1", "Week 2", etc.
            week_pattern = r'Week\s*(\d+)'
            match = re.search(week_pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
            return None
        except Exception as e:
            logger.error(f"Error extracting week number: {e}")
            return None

    def get_template_for_week(self, week_number: int) -> Optional[str]:
        """Find the appropriate template for the given week number"""
        try:
            # List all templates
            templates = [f for f in os.listdir(self.templates_dir) if f.endswith('.png')]
            
            # Look for template matching the week number
            for template in templates:
                if f"Week{week_number}" in template:
                    return os.path.join(self.templates_dir, template)
            
            logger.error(f"No template found for week {week_number}")
            return None
        except Exception as e:
            logger.error(f"Error finding template: {e}")
            return None

    def merge_header_with_template(self, source_image: str, template_path: str, header_proportion: float = 0.12) -> Optional[str]:
        """
        Copy header from source image to template.
        
        Args:
            source_image: Path to source image
            template_path: Path to template image
            header_proportion: Proportion of image height to use for header (default 0.12)
        """
        try:
            # Read images
            source = cv2.imread(source_image)
            template = cv2.imread(template_path)
            
            if source is None or template is None:
                logger.error("Failed to read source or template image")
                return None
            
            # Get dimensions
            source_height = source.shape[0]
            template_height = template.shape[0]
            template_width = template.shape[1]
            
            # Copy header using specified proportion
            header_height = int(source_height * header_proportion)
            template_header_height = int(template_height * header_proportion)
            
            # Extract header
            header = source[0:header_height, :]
            
            # Calculate the aspect ratio of the header
            header_aspect_ratio = header.shape[1] / header.shape[0]
            
            # Calculate new header width maintaining aspect ratio
            new_header_width = int(template_header_height * header_aspect_ratio)
            
            # Resize header maintaining aspect ratio
            header_resized = cv2.resize(header, (new_header_width, template_header_height))
            
            # Create new image
            result = template.copy()
            
            # Calculate centering position
            x_offset = (template_width - new_header_width) // 2
            
            # If header is wider than template, crop it from center
            if new_header_width > template_width:
                crop_start = (new_header_width - template_width) // 2
                header_resized = header_resized[:, crop_start:crop_start + template_width]
                x_offset = 0
            
            # Create the header region with white background
            header_region = np.full((template_header_height, template_width, 3), 255, dtype=np.uint8)
            
            # Place the resized header in the center
            if x_offset >= 0:
                header_region[:, x_offset:x_offset + header_resized.shape[1]] = header_resized
            
            # Copy the header region to the template
            result[0:template_header_height, :] = header_region
            
            # Save result with unique timestamp to avoid conflicts
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            output_path = os.path.join(
                self.temp_dir,
                f'merged_menu_{timestamp}.png'
            )
            
            # Save and verify
            success = cv2.imwrite(output_path, result)
            if not success:
                logger.error("Failed to save merged image")
                return None
                
            # Verify file was created and is valid
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.error("Merged file is missing or empty")
                return None
                
            # Verify the saved image can be read back
            test_img = cv2.imread(output_path)
            if test_img is None:
                logger.error("Saved merged image cannot be read back")
                return None
            
            logger.info(f"Successfully merged header with template: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error merging header with template: {e}")
            return None

    def extract_menu_info(self, text: str) -> Tuple[Optional[str], Optional[int]]:
        """Extract season and week number from text"""
        try:
            # Log the extracted text for debugging
            logger.info(f"Extracted text from menu:\n{text}")
            
            # Try to detect season from filename first
            season = None
            if 'summer' in text.lower():
                season = 'Summer'
            elif 'winter' in text.lower():
                season = 'Winter'
            
            # Try multiple patterns for week number
            week_patterns = [
                r'Week\s*(\d+)',  # "Week 1"
                r'W(?:ee)?k\.?\s*(\d+)',  # "Wk 1" or "Wk. 1"
                r'Menu\s+(\d+)',  # "Menu 1"
            ]
            
            week_number = None
            for pattern in week_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    week_number = int(match.group(1))
                    break
            
            # If we still don't have a week number, look for any single digit
            if not week_number:
                numbers = re.findall(r'\b\d\b', text)  # Single digits
                if len(numbers) == 1:  # If there's only one single digit in the text
                    week_number = int(numbers[0])
            
            if season and week_number:
                logger.info(f"Detected {season} Week {week_number}")
            else:
                logger.warning(f"Could not detect both season and week. Season: {season}, Week: {week_number}")
                logger.info("Looking for patterns in text...")
                # Log any numbers found
                numbers = re.findall(r'\d+', text)
                logger.info(f"Numbers found in text: {numbers}")
                # Log any words that might be seasons
                words = re.findall(r'\b\w+\b', text)
                logger.info(f"Words that might be seasons: {[w for w in words if 'summer' in w.lower() or 'winter' in w.lower()]}")
            
            # If we have a week number but no season, default to current season
            if week_number and not season:
                # Simple season detection based on month
                current_month = datetime.now().month
                season = 'Summer' if current_month in [12, 1, 2, 3, 4] else 'Winter'  # Southern Hemisphere
                logger.info(f"Using current season: {season}")
            
            return season, week_number
            
        except Exception as e:
            logger.error(f"Error extracting menu info: {e}")
            return None, None

    def get_template_for_menu(self, season: str, week_number: int) -> Optional[str]:
        """Find the appropriate template for the given season and week number"""
        try:
            # List all templates
            templates = [f for f in os.listdir(self.templates_dir) if f.endswith('.png')]
            logger.info(f"Available templates: {templates}")
            
            # Try different filename formats
            possible_names = [
                f"{season}Week{week_number}.png",     # SummerWeek1.png
                f"{season} Week{week_number}.png",    # Summer Week1.png
                f"{season}_Week_{week_number}.png",   # Summer_Week_1.png
                f"{season} Week {week_number}.png",   # Summer Week 1.png
            ]
            
            # Try each possible name
            for template_name in possible_names:
                if template_name in templates:
                    template_path = os.path.join(self.templates_dir, template_name)
                    # Verify template file is accessible and valid
                    if os.path.exists(template_path) and os.path.getsize(template_path) > 0:
                        # Try to read the template to verify it's a valid image
                        try:
                            test_img = cv2.imread(template_path)
                            if test_img is not None:
                                logger.info(f"Found and verified template: {template_path}")
                                return template_path
                            else:
                                logger.error(f"Template file exists but cannot be read as image: {template_path}")
                        except Exception as e:
                            logger.error(f"Error reading template file: {e}")
                    else:
                        logger.error(f"Template file invalid or inaccessible: {template_path}")
            
            # If no exact match, try case-insensitive search
            template_name_lower = f"{season.lower()}week{week_number}".replace(" ", "")
            for template in templates:
                if template_name_lower in template.lower().replace(" ", ""):
                    template_path = os.path.join(self.templates_dir, template)
                    # Verify template file is accessible and valid
                    if os.path.exists(template_path) and os.path.getsize(template_path) > 0:
                        try:
                            test_img = cv2.imread(template_path)
                            if test_img is not None:
                                logger.info(f"Found and verified template (case-insensitive): {template_path}")
                                return template_path
                            else:
                                logger.error(f"Template file exists but cannot be read as image: {template_path}")
                        except Exception as e:
                            logger.error(f"Error reading template file: {e}")
                    else:
                        logger.error(f"Template file invalid or inaccessible: {template_path}")
            
            logger.error(f"No valid template found for {season} Week {week_number}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding template: {e}")
            return None

    def process_pdf_attachment(self, attachment_data: bytes, original_filename: str) -> Tuple[List[str], Optional[Dict[str, str]]]:
        """Process PDF attachment and return paths to images and extracted dates"""
        # Save PDF to temp file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            temp_pdf.write(attachment_data)
            pdf_path = temp_pdf.name

        try:
            # Convert to images
            output_folder = os.path.join(self.temp_dir, datetime.now().strftime('%Y%m%d_%H%M%S'))
            os.makedirs(output_folder, exist_ok=True)
            logger.info(f"Converting PDF to images in folder: {output_folder}")
            
            image_paths = convert_pdf_to_images(pdf_path, output_folder, self.poppler_path)
            
            if not image_paths:
                logger.error("No images were generated from PDF")
                return [], None
                
            logger.info(f"Generated {len(image_paths)} images from PDF")
            
            # Correct orientation for each image
            corrected_paths = []
            processed_paths = []
            
            for i, img_path in enumerate(image_paths):
                # Correct orientation
                corrected_path = os.path.join(output_folder, f"corrected_{os.path.basename(img_path)}")
                correct_orientation(img_path, corrected_path)
                if not os.path.exists(corrected_path):
                    logger.warning(f"Failed to correct orientation for {img_path}, using original")
                    corrected_path = img_path
                corrected_paths.append(corrected_path)
                
                # Extract text and detect menu info for each page
                page = Image.open(corrected_path)
                text = pytesseract.image_to_string(page)
                logger.info(f"Page {i+1} text:\n{text}")
                
                season, week_number = self.extract_menu_info(text)
                if season and week_number:
                    logger.info(f"Page {i+1}: Detected {season} Week {week_number}")
                    template_path = self.get_template_for_menu(season, week_number)
                    
                    if template_path:
                        # Use a larger header proportion for all weeks to ensure dates are covered
                        header_proportion = 0.17  # Increased to 17% for all weeks
                        
                        # Try merging with template
                        merged_path = self.merge_header_with_template(
                            corrected_path, 
                            template_path, 
                            header_proportion=header_proportion
                        )
                        
                        if merged_path:
                            # Verify merged result
                            try:
                                test_img = cv2.imread(merged_path)
                                if test_img is not None and test_img.shape[0] > 0 and test_img.shape[1] > 0:
                                    logger.info(f"Successfully verified merged result for page {i+1}")
                                    processed_paths.append(merged_path)
                                    continue
                                else:
                                    logger.error(f"Merged result invalid for page {i+1}")
                            except Exception as e:
                                logger.error(f"Error verifying merged result: {e}")
                
                # If we couldn't process with template, use corrected image
                logger.warning(f"Using corrected image for page {i+1} (no template processing)")
                processed_paths.append(corrected_path)
            
            if not processed_paths:
                logger.error("No pages were successfully processed")
                return [], None
                
            logger.info(f"Successfully processed {len(processed_paths)} pages")
            return processed_paths, None
            
        except Exception as e:
            logger.error(f"Error processing PDF attachment: {e}")
            return [], None
        finally:
            try:
                os.unlink(pdf_path)  # Clean up temp PDF
            except Exception as e:
                logger.error(f"Error cleaning up temporary PDF: {e}")

    def send_response_email(self, recipient: str, processed_images: List[str]):
        """
        Send the processed menu images back via email.
        
        Args:
            recipient: Email address to send to
            processed_images: List of paths to the processed menu images
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['To'] = recipient
            msg['Subject'] = "Processed Menu Images - Holly Lodge"

            # Add detailed body text
            body = f"""Hello,

I have processed the menu PDF you sent and converted it to images.
I am attaching {len(processed_images)} processed image(s).

These images are ready to be used for the Holly Lodge menu system.

Best regards,
Holly Lodge Menu System"""

            msg.attach(MIMEText(body, 'plain'))

            # Attach images
            for i, image_path in enumerate(processed_images, 1):
                with open(image_path, 'rb') as f:
                    img_data = f.read()
                    image = MIMEImage(img_data)
                    # Set a more descriptive filename
                    filename = f"Holly_Lodge_Menu_Page_{i}.png"
                    image.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(image)

            # Connect to SMTP server and send
            with smtplib.SMTP(self.config['email']['smtp_server'], self.config['email']['smtp_port']) as server:
                server.starttls()
                server.login(self.email, self.password)
                server.send_message(msg)

            logger.info(f"Successfully sent processed menu to {recipient}")

        except Exception as e:
            logger.error(f"Error sending response email: {e}")
            raise

    def process_new_emails(self):
        """Process new unread emails in the Menus folder"""
        try:
            print("\n🔍 Starting email processing...")
            mail = self.connect()
            mail.select('Menus')
            
            # Search for unread messages
            _, message_numbers = mail.search(None, 'UNSEEN')
            message_list = message_numbers[0].split()
            
            if not message_list:
                print("📭 No unread messages found")
                return
            
            print(f"📬 Found {len(message_list)} unread messages")
            
            for msg_num in message_list:
                try:
                    print(f"\n📨 Processing message {msg_num.decode()}...")
                    
                    # Get message ID first for tracking
                    _, msg_data = mail.fetch(msg_num, '(RFC822)')
                    email_body = msg_data[0][1]
                    message = email.message_from_bytes(email_body)
                    message_id = message['Message-ID']
                    
                    # Skip if already processed
                    if self.is_email_processed(mail, message_id):
                        print("✓ Message already processed, skipping")
                        continue
                    
                    print("📎 Looking for attachments...")
                    processed_images = []
                    dates_info = None
                    
                    # Process attachments
                    for part in message.walk():
                        if part.get_content_maintype() == 'multipart':
                            continue
                        if part.get('Content-Disposition') is None:
                            continue
                            
                        filename = part.get_filename()
                        if not filename:
                            continue
                            
                        print(f"📄 Found attachment: {filename}")
                        
                        if filename.lower().endswith('.pdf'):
                            print("🔄 Processing PDF attachment...")
                            attachment_data = part.get_payload(decode=True)
                            images, dates = self.process_pdf_attachment(attachment_data, filename)
                            if images:
                                processed_images.extend(images)
                                dates_info = dates
                                print(f"✨ Successfully processed PDF into {len(images)} images")
                    
                    if processed_images:
                        print("\n📧 Preparing to send response email...")
                        sender_email = message['From']
                        print(f"📤 Sending to: {sender_email}")
                        
                        print("⏳ Starting email send process...")
                        self.send_response_email(sender_email, processed_images)
                        print("✅ Response email sent successfully")
                        
                        # Mark as processed only after successful send
                        print("📝 Marking email as processed...")
                        self.mark_as_processed(mail, msg_num, message_id)
                        print("✓ Email marked as processed")
                        
                    else:
                        print("⚠️ No processable attachments found")
                    
                except Exception as e:
                    print(f"❌ Error processing message: {str(e)}")
                    continue
            
            print("\n✨ Email processing complete!")
            
        except Exception as e:
            print(f"❌ Error in process_new_emails: {str(e)}")
            raise

def main():
    logger.info("Starting Menu Email Monitor")
    logger.info("Press Ctrl+C to stop the monitor")
    logger.info("Monitoring 'Menus' folder for new emails...")
    logger.info(f"Email account being monitored: {os.getenv('SMTP_USERNAME')}")
    
    monitor = MenuEmailMonitor()
    
    try:
        while True:
            try:
                logger.info("Checking Menus folder for new emails...")
                monitor.process_new_emails()
                logger.info("Waiting 3 minutes before next check...")
                time.sleep(180)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                logger.info("Waiting 1 minute before retry...")
                time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down Menu Email Monitor...")
        logger.info("Cleaning up temporary files...")
        monitor.cleanup_old_files(max_age_hours=0)
        logger.info("Shutdown complete")

if __name__ == "__main__":
    main() 