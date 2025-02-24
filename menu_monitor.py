import os
import sys
import imaplib
import email
import tempfile
import shutil
from email.header import decode_header
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any
import logging
from ProcessToImage import convert_pdf_to_images, correct_orientation
from menu_scheduler import load_config
from menu_utils import add_dates_to_menu
import re
import pytesseract
from PIL import Image, ImageDraw, ImageEnhance
import cv2
import numpy as np
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
import yaml
import platform
from pdf2image import convert_from_path
import subprocess
import gc

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
        """Initialize the menu email monitor"""
        try:
            print("Initializing MenuEmailMonitor...")
            
            # Load configuration
            print("Loading configuration...")
            with open('config.yaml', 'r') as f:
                self.config = yaml.safe_load(f)
            
            # Set up email credentials
            print("Setting up email credentials...")
            self.email = os.getenv('SMTP_USERNAME')
            self.password = os.getenv('SMTP_PASSWORD')
            
            if not self.email or not self.password:
                raise ValueError("Email credentials not found in environment variables")
            
            # Create required directories
            print("Setting up directories...")
            self.ensure_folders()
            
            # Verify Tesseract installation
            if not self.verify_tesseract_installation():
                logger.warning("⚠️ Tesseract verification failed - OCR functionality may be limited")
            
            print("MenuEmailMonitor initialized successfully")
            
        except Exception as e:
            print(f"Failed to initialize MenuEmailMonitor: {str(e)}")
            raise

    def ensure_folders(self):
        """Ensure required folders exist"""
        try:
            required_folders = [
                'temp_images',
                'output_images',
                'menu_templates'
            ]
            
            for folder in required_folders:
                if not os.path.exists(folder):
                    print(f"Creating folder: {folder}")
                    os.makedirs(folder)
            
        except Exception as e:
            print(f"Failed to create required folders: {str(e)}")
            raise

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
                'temp_images',  # temp_images
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
            mail = imaplib.IMAP4_SSL(self.config['email'].get('imap_server', 'imap.gmail.com'))
            mail.login(self.email, self.password)
            logger.info("Successfully connected to IMAP server")
            return mail
        except Exception as e:
            logger.error(f"Failed to connect to IMAP server: {e}")
            raise

    def extract_dates_from_image(self, image_path: str) -> Optional[Dict[str, str]]:
        """Extract dates from the image using OCR"""
        try:
            # Open and optimize image for OCR
            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode not in ('L', 'RGB'):
                    img = img.convert('RGB')
                
                # Resize if too large (max dimension 2400px)
                max_dimension = 2400
                if max(img.size) > max_dimension:
                    ratio = max_dimension / max(img.size)
                    new_size = tuple(int(dim * ratio) for dim in img.size)
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Enhance image for OCR
                img = ImageEnhance.Contrast(img).enhance(1.5)
                img = ImageEnhance.Sharpness(img).enhance(1.5)
                
                # Convert to grayscale for OCR
                img = img.convert('L')
                
                # Use custom OCR config for better memory usage
                custom_config = '--psm 6 --oem 1'
                text = pytesseract.image_to_string(img, config=custom_config)
                
                # Clean up memory
                img = None
                
            # Process text to extract dates
            dates = {}
            lines = text.split('\n')
            for line in lines:
                # Process one line at a time
                match = re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s+(\d+(?:st|nd|rd|th)?\s+[A-Za-z]+)', line)
                if match:
                    day = match.group(1)[:3]  # Standardize to 3 letters
                    date = match.group(2)
                    dates[day] = date
            
            return dates if dates else None
            
        except Exception as e:
            print(f"Error extracting dates: {str(e)}")
            return None
        finally:
            # Ensure we clean up any temporary files
            if 'img' in locals():
                del img
            gc.collect()

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
            templates = [f for f in os.listdir(self.config['templates_dir']) if f.endswith('.png')]
            
            # Look for template matching the week number
            for template in templates:
                if f"Week{week_number}" in template:
                    return os.path.join(self.config['templates_dir'], template)
            
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
                self.config['temp_dir'],
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
            templates = [f for f in os.listdir(self.config['templates_dir']) if f.endswith('.png')]
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
                    template_path = os.path.join(self.config['templates_dir'], template_name)
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
                    template_path = os.path.join(self.config['templates_dir'], template)
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
        """Process a PDF attachment and extract dates"""
        temp_dir = None
        processed_images = []
        dates = None
        
        try:
            # Create temporary directory
            temp_dir = os.path.join(os.getcwd(), 'temp_images')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Save PDF to temp file
            pdf_path = os.path.join(temp_dir, 'temp.pdf')
            with open(pdf_path, 'wb') as f:
                f.write(attachment_data)
            
            # Convert PDF to images
            print(f"Converting PDF: {original_filename}")
            poppler_path = None if platform.system() != 'Windows' else r'C:\Poppler\Release-24.08.0-0\poppler-24.08.0\Library\bin'
            
            # Process one page at a time
            images = convert_from_path(pdf_path, poppler_path=poppler_path)
            for i, image in enumerate(images):
                try:
                    # Save image with optimized settings
                    image_path = os.path.join(temp_dir, f'page_{i + 1}.png')
                    image.save(image_path, 'PNG', optimize=True)
                    processed_images.append(image_path)
                    
                    # Try to extract dates from this image
                    if dates is None:
                        dates = self.extract_dates_from_image(image_path)
                    
                    # Clean up memory after each page
                    image = None
                    gc.collect()
                    
                except Exception as e:
                    print(f"Error processing page {i + 1}: {str(e)}")
                    continue
            
            return processed_images, dates
            
        except Exception as e:
            print(f"Error processing PDF: {str(e)}")
            return [], None
            
        finally:
            # Clean up temporary files
            try:
                if temp_dir and os.path.exists(temp_dir):
                    for file in os.listdir(temp_dir):
                        if file != 'temp.pdf' and not any(file in img for img in processed_images):
                            os.remove(os.path.join(temp_dir, file))
            except Exception as e:
                print(f"Error cleaning up temp files: {str(e)}")
            gc.collect()

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

    def verify_tesseract_installation(self) -> bool:
        """Verify Tesseract OCR is installed and working"""
        try:
            print("\n=== Tesseract Verification Start ===")
            
            # Log environment info
            print(f"Environment: Render={os.getenv('RENDER', 'false')}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"Directory contents: {os.listdir()}")
            print(f"PATH environment: {os.getenv('PATH')}")
            
            # Check environment variables
            tesseract_path = os.getenv('TESSERACT_PATH')
            tessdata_prefix = os.getenv('TESSDATA_PREFIX')
            ld_library_path = os.getenv('LD_LIBRARY_PATH')
            
            print(f"TESSERACT_PATH: {tesseract_path}")
            print(f"TESSDATA_PREFIX: {tessdata_prefix}")
            print(f"LD_LIBRARY_PATH: {ld_library_path}")
            
            # Check for local installation first
            local_paths = [
                os.path.join(os.getcwd(), 'bin', 'tesseract'),  # Our local copy
                tesseract_path,  # Environment variable path
                '/usr/bin/tesseract',  # System path
                '/usr/local/bin/tesseract',  # Alternative system path
                shutil.which('tesseract')  # PATH search
            ]
            
            tesseract_binary = None
            for path in local_paths:
                if path and os.path.isfile(path):
                    print(f"✅ Found Tesseract at: {path}")
                    tesseract_binary = path
                    break
            
            if not tesseract_binary:
                print("❌ Tesseract binary not found in any location")
                return False
                
            # Set the Tesseract command for pytesseract
            pytesseract.pytesseract.tesseract_cmd = tesseract_binary
            
            try:
                # Test Tesseract version
                version = pytesseract.get_tesseract_version()
                print(f"✅ Tesseract version: {version}")
                
                # Test available languages
                langs = pytesseract.get_languages()
                print(f"✅ Available languages: {langs}")
                
                # Create a test image
                test_image = Image.new('RGB', (200, 50), color='white')
                draw = ImageDraw.Draw(test_image)
                draw.text((10, 10), "TEST OCR 123", fill='black')
                test_image_path = 'test_ocr.png'
                test_image.save(test_image_path)
                
                # Test OCR functionality
                try:
                    text = pytesseract.image_to_string(test_image)
                    print(f"✅ OCR Test result: {text.strip()}")
                    os.remove(test_image_path)
                    return True
                except Exception as e:
                    print(f"❌ OCR Test failed: {str(e)}")
                    if os.path.exists(test_image_path):
                        os.remove(test_image_path)
                    return False
                    
            except Exception as e:
                print(f"❌ Tesseract verification failed: {str(e)}")
                return False
                
        except Exception as e:
            print(f"❌ Error during verification: {str(e)}")
            return False
        finally:
            print("=== Tesseract Verification End ===\n")

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