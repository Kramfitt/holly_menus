from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import time
import os
from werkzeug.utils import secure_filename
import traceback
import random
import string
import re
from PIL import Image

from app.utils.logger import get_logger
from app.utils.debug import debug_log, debug_print, is_debug_mode
from app.utils.tesseract_config import optimize_image_for_ocr, perform_ocr

class MenuService:
    def __init__(self, db, storage):
        self.db = db
        self.storage = storage
        self.template_bucket = 'menu-templates'
        self.menus_bucket = 'menus'
        self._ensure_bucket_exists()
        
    @debug_log("Bucket Check", timing=True)
    def _ensure_bucket_exists(self):
        """Ensure storage bucket exists"""
        try:
            debug_print("\n=== Checking Storage Bucket ===")
            debug_print(f"Bucket name: {self.template_bucket}")
            
            # Try to get bucket info first
            try:
                debug_print("Checking if bucket exists...")
                bucket_info = self.storage.from_(self.template_bucket).list()
                if bucket_info is not None:  # If we can list files, bucket exists
                    debug_print("✅ Bucket exists and is accessible")
                    return True
            except Exception as e:
                debug_print(f"⚠️ Bucket info check failed: {str(e)}")
                debug_print("Attempting bucket creation...")
            
            try:
                # Create bucket with required parameters
                debug_print("Creating new bucket with parameters:")
                debug_print("- public: True")
                debug_print("- file_size_limit: 5MB")
                debug_print("- allowed_mime_types: ['image/jpeg', 'image/png', 'application/pdf']")
                
                self.storage.create_bucket(
                    self.template_bucket,
                    options={
                        'public': True,
                        'file_size_limit': 5242880,  # 5MB
                        'allowed_mime_types': ['image/jpeg', 'image/png', 'application/pdf']
                    }
                )
                
                get_logger().log_activity(
                    action="Bucket Created",
                    details={
                        "bucket": self.template_bucket,
                        "options": {
                            "public": True,
                            "file_size_limit": "5MB",
                            "allowed_mime_types": ["image/jpeg", "image/png", "application/pdf"]
                        }
                    },
                    status="success"
                )
                
                debug_print("✅ Created new bucket successfully")
                time.sleep(1)  # Wait for bucket to be ready
                
                # Verify bucket was created
                debug_print("Verifying new bucket...")
                verify = self.storage.from_(self.template_bucket).list()
                if verify is not None:
                    debug_print("✅ New bucket verified and accessible")
                    return True
                else:
                    debug_print("❌ Bucket creation succeeded but verification failed")
                    return False
                
            except Exception as e:
                debug_print(f"❌ Bucket creation failed: {str(e)}")
                debug_print("Full error details:", traceback.format_exc())
                get_logger().log_activity(
                    action="Template Bucket Creation Failed",
                    details={
                        "error": str(e),
                        "traceback": traceback.format_exc()
                    },
                    status="error"
                )
                return False
            
        except Exception as e:
            debug_print(f"❌ Bucket check failed: {str(e)}")
            debug_print("Full error details:", traceback.format_exc())
            get_logger().log_activity(
                action="Bucket Check Failed",
                details={
                    "error": str(e),
                    "traceback": traceback.format_exc()
                },
                status="error"
            )
            return False
    
    @debug_log("Calculate Next Menu", timing=True)
    def calculate_next_menu(self):
        """Calculate which menu should be sent next"""
        try:
            # Get current settings
            settings_response = self.db.table('menu_settings')\
                .select('*')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()

            if not settings_response.data:
                debug_print("No menu settings found")
                return None

            settings = settings_response.data[0]
            start_date = datetime.strptime(settings['start_date'], '%Y-%m-%d').date()
            today = datetime.now().date()

            # Calculate next menu period
            days_since_start = (today - start_date).days
            weeks_since_start = days_since_start // 7
            current_period = weeks_since_start // 2
            
            # Calculate next period start
            next_period_start = start_date + timedelta(weeks=current_period * 2)
            if today >= next_period_start:
                next_period_start += timedelta(weeks=2)

            # Calculate send date
            send_date = next_period_start - timedelta(days=settings['days_in_advance'])

            # Determine season and week
            season = settings['season']
            week_pair = "1_2" if (current_period % 2 == 0) else "3_4"

            result = {
                'send_date': send_date,
                'period_start': next_period_start,
                'season': season,
                'menu_pair': week_pair
            }
            
            debug_print("Calculated next menu:", result)
            return result

        except Exception as e:
            debug_print("Error calculating next menu:", str(e))
            return None
    
    @debug_log("Get Settings", timing=True)
    def get_settings(self) -> Optional[Dict[str, Any]]:
        """Get current menu settings"""
        try:
            response = self.db.table('menu_settings')\
                .select('*')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
                
            if not response.data:
                debug_print("No settings found")
                return None
                
            settings = response.data[0]
            
            # Convert date strings to date objects
            settings['start_date'] = datetime.strptime(
                settings['start_date'], '%Y-%m-%d'
            ).date()
            
            if settings.get('season_change_date'):
                settings['season_change_date'] = datetime.strptime(
                    settings['season_change_date'], '%Y-%m-%d'
                ).date()
                
            debug_print("Retrieved settings:", settings)
            return settings
            
        except Exception as e:
            debug_print("Error getting settings:", str(e))
            return None
    
    def _determine_season(self, date: datetime.date, settings: Dict[str, Any]) -> str:
        """Determine the season for a given date"""
        if not settings.get('season_change_date'):
            return settings['season']
            
        current_season = settings['season']
        change_date = settings['season_change_date']
        
        # Convert string date to datetime if needed
        if isinstance(change_date, str):
            change_date = datetime.strptime(change_date, '%Y-%m-%d').date()
        
        if date >= change_date:
            return 'winter' if current_season == 'summer' else 'summer'
            
        return current_season
    
    def _create_response(self, data: Optional[Dict[str, Any]], error: Optional[str] = None) -> Dict[str, Any]:
        """Create a standardized response format"""
        return {
            'data': data,
            'error': error,
            'success': data is not None
        }

    def get_menu_template(self):
        """Handle menu template retrieval"""
        pass

    @debug_log("Save Template", timing=True)
    def save_template(self, file, season: str, week: str):
        """Save a menu template to storage and database."""
        try:
            debug_print("\n=== Starting Template Save ===")
            debug_print(f"Input parameters:")
            debug_print(f"- File: {file.filename}")
            debug_print(f"- Content Type: {file.content_type}")
            debug_print(f"- Season: {season}")
            debug_print(f"- Week: {week}")
            
            # Validate inputs
            if not file or not season:
                debug_print("❌ Missing required parameters")
                raise ValueError("Missing required parameters")
            
            # Convert season to lowercase and validate EXACTLY against allowed values
            season = season.strip().lower()  # Remove any whitespace and convert to lowercase
            allowed_seasons = {'summer', 'winter', 'dates'}
            if season not in allowed_seasons:
                debug_print(f"❌ Invalid season: '{season}'")
                raise ValueError(f"Invalid season: '{season}'. Must be exactly one of: summer, winter, dates")
            
            # Validate week based on season
            debug_print("Validating week number...")
            if season == 'dates':
                week_num = 0  # Dates templates always use week 0
                debug_print("Using week 0 for dates template")
            else:
                if not week:
                    debug_print("❌ Week is required for summer/winter templates")
                    raise ValueError("Week is required for summer/winter templates")
                try:
                    week_num = int(week)
                    if not 1 <= week_num <= 4:
                        debug_print(f"❌ Invalid week number: {week_num}")
                        raise ValueError("Week must be between 1 and 4 for summer/winter templates")
                    debug_print(f"Week number validated: {week_num}")
                except ValueError:
                    debug_print("❌ Invalid week number format")
                    raise ValueError("Invalid week number")
            
            # Ensure storage bucket exists
            debug_print("\nVerifying storage bucket...")
            if not self._ensure_bucket_exists():
                debug_print("❌ Failed to ensure storage bucket exists")
                raise Exception("Failed to ensure storage bucket exists")
            debug_print("✅ Storage bucket verified")
            
            # First, check if a template already exists and delete it from the database
            debug_print("\nChecking for existing template...")
            try:
                existing = self.db.table('menu_templates')\
                    .delete()\
                    .eq('season', season)\
                    .eq('week', week_num)\
                    .execute()
                if existing.data:
                    debug_print(f"Deleted existing template record")
            except Exception as e:
                debug_print(f"⚠️ Error checking/deleting existing template: {str(e)}")
            
            # Clean up existing files in storage
            debug_print("\nCleaning up existing files...")
            self._cleanup_old_template(season, week_num)
            
            # Generate unique filename with organized folder structure
            timestamp = int(time.time() * 1000)
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            file_ext = os.path.splitext(file.filename)[1].lower()
            if not file_ext:
                file_ext = '.png'  # Default to .png if no extension

            # Organize files into season-specific folders
            if season == 'dates':
                filename = f"dates/header_{timestamp}_{random_suffix}{file_ext}"
            else:
                filename = f"{season}/week_{week_num}_{timestamp}_{random_suffix}{file_ext}"
            debug_print(f"Generated filename: {filename}")
            
            # Upload new template
            debug_print("\nUploading new template...")
            file_data = file.read()
            file.seek(0)  # Reset file pointer
            
            try:
                debug_print("Attempting storage upload...")
                upload_response = self.storage.from_(self.template_bucket).upload(
                    path=filename,
                    file=file_data,
                    file_options={"content-type": file.content_type}
                )
                
                if not upload_response:
                    debug_print("❌ Upload failed - no response from storage")
                    raise Exception("Upload failed - no response from storage")
                
                debug_print("✅ Upload successful")
                debug_print("Upload response:", upload_response)
                
                # Get public URL - retry up to 3 times
                debug_print("\nGetting public URL...")
                template_url = None
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        template_url = self.storage.from_(self.template_bucket).get_public_url(filename)
                        if template_url:
                            debug_print(f"Got public URL on attempt {attempt + 1}: {template_url}")
                            break
                        debug_print(f"No URL returned on attempt {attempt + 1}, retrying...")
                        time.sleep(1)  # Wait before retry
                    except Exception as url_error:
                        debug_print(f"Error getting URL on attempt {attempt + 1}: {str(url_error)}")
                        if attempt == max_retries - 1:
                            raise Exception(f"Failed to get public URL after {max_retries} attempts: {str(url_error)}")
                        time.sleep(1)  # Wait before retry
                
                if not template_url:
                    debug_print("❌ Failed to get public URL")
                    raise Exception("Failed to get public URL for uploaded file")
                
                # Insert new record into database
                debug_print("\nInserting into database...")
                
                # Ensure data matches schema constraints exactly
                db_data = {
                    'season': season,  # Will be exactly 'summer', 'winter', or 'dates'
                    'week': week_num,  # Will be 0 for dates, 1-4 for summer/winter
                    'template_url': template_url,
                    'file_path': filename
                }
                
                debug_print("Database data:", db_data)
                
                # Insert new record
                debug_print("Executing database insert...")
                db_response = self.db.table('menu_templates')\
                    .insert(db_data)\
                    .execute()
                
                if not db_response.data:
                    debug_print("❌ Database insert failed - no response")
                    raise Exception("Database insert failed - no response")
                
                debug_print("✅ Database updated successfully")
                debug_print("=== Template Save Complete ===\n")
                
                return {
                    'success': True, 
                    'message': 'Template saved successfully',
                    'url': template_url
                }
                
            except Exception as e:
                debug_print(f"\n❌ Error during upload/database update: {str(e)}")
                # Try to clean up failed upload
                try:
                    debug_print("Attempting to clean up failed upload...")
                    self.storage.from_(self.template_bucket).remove([filename])
                    debug_print("Cleanup successful")
                except Exception as cleanup_error:
                    debug_print(f"⚠️ Cleanup failed: {str(cleanup_error)}")
                raise e
            
        except Exception as e:
            debug_print("\n❌ Error in save_template:")
            debug_print(f"Error message: {str(e)}")
            debug_print("Full error details:", traceback.format_exc())
            return {
                'success': False, 
                'error': str(e)
            }

    def get_templates(self):
        """Get all templates organized by season"""
        try:
            response = self.db.table('menu_templates').select('*').execute()
            templates = {
                'summer': {}, 
                'winter': {},
                'dates': {}  # Add dates section
            }
            
            for template in response.data:
                season = template['season']
                week = str(template['week']) if season not in ['dates'] else 'header'
                templates[season][week] = {
                    'template_url': template.get('template_url'),
                    'file_path': template.get('file_path'),
                    'updated_at': template['updated_at']
                }
            
            return templates
        except Exception as e:
            get_logger().log_activity(
                action="Template Fetch Failed",
                details=str(e),
                status="error"
            )
            return {'summer': {}, 'winter': {}, 'dates': {}}

    def get_template(self, season, week):
        """Get a specific template"""
        try:
            query = self.db.table('menu_templates')\
                .select('*')\
                .eq('season', season.lower())
            
            # Handle dates template differently
            if season.lower() == 'dates':
                query = query.eq('week', 0)  # For dates template, week should be 0
            else:
                query = query.eq('week', int(week))
                
            response = query.execute()
                
            if not response.data:
                return None
                
            return response.data[0]
            
        except Exception as e:
            get_logger().log_activity(
                action="Template Fetch Failed",
                details=f"Error fetching template for {season} week {week}: {str(e)}",
                status="error"
            )
            return None

    def generate_preview(self, template, start_date):
        """Generate a preview of the menu template."""
        if not template or not start_date:
            raise ValueError("Template and start date are required")

        required_fields = ['season', 'week', 'template_url']
        for field in required_fields:
            if field not in template:
                raise ValueError(f"Template is missing required field: {field}")

        # Get the dates template
        dates_template = self.get_template('dates', 0)
        if not dates_template:
            raise ValueError("Dates header template not found")
        
        dates_template_url = dates_template.get('template_url')
        if not dates_template_url:
            raise ValueError("Invalid dates template URL")

        # Calculate date range
        period_start = start_date.date()
        period_end = period_start + timedelta(days=13)
        date_range = f"{period_start.strftime('%d %b')} - {period_end.strftime('%d %b %Y')}"

        # Merge the templates
        merged_template = self.merge_header_with_template(
            source_image=dates_template_url,
            template_path=template['template_url'],
            header_proportion=0.20  # Header takes up 20% of the height
        )

        if not merged_template:
            raise ValueError("Failed to merge templates")

        return {
            'template': {
                'season': template['season'],
                'week': template['week'],
                'template_url': merged_template,
                'date_range': date_range
            }
        }

    def _validate_file(self, file):
        """Validate uploaded file"""
        try:
            # Basic checks
            if not file or not file.filename:
                raise ValueError("No valid file provided")
            
            # Check file type and extension match
            allowed_types = {
                'application/pdf': ['.pdf'],
                'image/jpeg': ['.jpg', '.jpeg'],
                'image/png': ['.png']
            }
            
            ext = os.path.splitext(file.filename)[1].lower()
            if file.content_type not in allowed_types:
                raise ValueError(f"Invalid file type. Allowed types: PDF, JPEG, PNG")
            
            if ext not in allowed_types[file.content_type]:
                raise ValueError(f"File extension doesn't match its content type")
            
            # Check file size (5MB limit)
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)
            
            if size > 5 * 1024 * 1024:
                raise ValueError("File size exceeds 5MB limit")
            
            # Basic content check
            try:
                content = file.read(1024)  # Read first 1KB
                file.seek(0)
                
                # Check for common file signatures
                if file.content_type == 'application/pdf' and not content.startswith(b'%PDF'):
                    raise ValueError("Invalid PDF file")
                elif file.content_type == 'image/jpeg' and not content.startswith(b'\xFF\xD8'):
                    raise ValueError("Invalid JPEG file")
                elif file.content_type == 'image/png' and not content.startswith(b'\x89PNG'):
                    raise ValueError("Invalid PNG file")
                
                return True
                
            except Exception as e:
                raise ValueError(f"File content validation failed: {str(e)}")
            
        except ValueError as e:
            raise e
        except Exception as e:
            get_logger().log_activity(
                action="File Validation Failed",
                details=str(e),
                status="error"
            )
            raise ValueError(f"File validation failed: {str(e)}")

    def _cleanup_old_template(self, season, week):
        """Remove old template if it exists"""
        try:
            old_template = self.get_template(season, week)
            if old_template and old_template.get('file_path'):
                # Backup first
                self._backup_template(old_template)
                
                # Then delete from original location
                try:
                    # Delete both from potential locations (old and new structure)
                    paths_to_check = [
                        old_template['file_path'],
                        f"{season}/week_{week}_{os.path.basename(old_template['file_path'])}",
                        f"templates/{season}_week_{week}_{os.path.basename(old_template['file_path'])}"
                    ]
                    
                    for path in paths_to_check:
                        try:
                            self.storage.from_(self.template_bucket).remove([path])
                            debug_print(f"Cleaned up file: {path}")
                        except Exception as e:
                            debug_print(f"Note: Could not delete {path}: {str(e)}")
                    
                    get_logger().log_activity(
                        action="Template Cleanup",
                        details={
                            'file_path': old_template['file_path'],
                            'file_type': old_template.get('file_type'),
                            'file_size': old_template.get('file_size')
                        },
                        status="success"
                    )
                except Exception as e:
                    get_logger().log_activity(
                        action="Template Cleanup Failed",
                        details=str(e),
                        status="warning"
                    )
        except Exception as e:
            get_logger().log_activity(
                action="Template Cleanup Error",
                details=str(e),
                status="error"
            )

    def _backup_template(self, template):
        """Create backup of template before deletion"""
        try:
            if not template or not template.get('file_path'):
                return
            
            # Create backup path with organized structure
            season = template['season']
            week = template['week']
            filename = os.path.basename(template['file_path'])
            
            if season == 'dates':
                backup_path = f"backup/dates/header_{filename}"
            else:
                backup_path = f"backup/{season}/week_{week}_{filename}"
            
            # Copy file to backup
            content = self.storage.from_(self.template_bucket).download(template['file_path'])
            self.storage.from_(self.template_bucket).upload(
                backup_path,
                content,
                {'content-type': template.get('file_type', 'application/octet-stream')}
            )
            
            get_logger().log_activity(
                action="Template Backup",
                details=f"Backed up template: {template['file_path']} → {backup_path}",
                status="success"
            )
            
        except Exception as e:
            get_logger().log_activity(
                action="Template Backup Failed",
                details=str(e),
                status="warning"
            )

    def delete_template(self, season: str, week: int) -> Dict[str, Any]:
        """Delete a menu template"""
        try:
            print(f"\n=== Starting Template Deletion ===")
            print(f"Season: {season}, Week: {week}")
            
            # Get the template first
            template = self.get_template(season, week)
            if not template:
                print("Template not found")
                return {'error': 'Template not found'}
            
            print(f"Found template: {template}")
            
            # Delete from storage first
            try:
                print("\n=== Deleting from Storage ===")
                files = self.storage.from_('menu-templates').list()
                pattern = f"templates/{season.lower()}_week_{week}"
                matching_files = [f for f in files if f['name'].startswith(pattern)]
                
                print(f"Found {len(matching_files)} matching files to delete")
                for file_obj in matching_files:
                    print(f"Deleting: {file_obj['name']}")
                    self.storage.from_('menu-templates').remove([file_obj['name']])
                    time.sleep(0.5)
                    print(f"Deleted: {file_obj['name']}")
            except Exception as e:
                print(f"Error deleting from storage: {str(e)}")
            
            # Wait for storage deletion
            time.sleep(1)
            
            print("\n=== Deleting from Database ===")
            # Delete from database
            query = self.db.table('menu_templates')\
                .delete()\
                .eq('season', season.lower())
                
            # Handle dates template differently
            if season.lower() == 'dates':
                query = query.is_('week', None)
            else:
                query = query.eq('week', int(week))
                
            query.execute()
            print("Database deletion complete")
            
            get_logger().log_activity(
                action="Template Deleted",
                details=f"Deleted template for {season} week {week}",
                status="success"
            )
            
            print("\n=== Deletion Complete ===")
            return {'success': True}
            
        except Exception as e:
            print(f"\n=== Deletion Failed ===\nError: {str(e)}")
            get_logger().log_activity(
                action="Template Delete Failed",
                details=str(e),
                status="error"
            )
            return {'error': str(e)}

    def merge_header_with_template(self, source_image: str, template_path: str, header_proportion: float = 0.20) -> Optional[str]:
        """
        Merge the dates header with the menu template.
        
        Args:
            source_image: URL of the dates header image
            template_path: URL of the menu template image
            header_proportion: Proportion of image height to use for header
        
        Returns:
            URL of the merged image
        """
        try:
            import cv2
            import numpy as np
            import requests
            from io import BytesIO
            
            # Download images from URLs
            header_response = requests.get(source_image)
            template_response = requests.get(template_path)
            
            # Convert to numpy arrays
            header_array = np.frombuffer(header_response.content, np.uint8)
            template_array = np.frombuffer(template_response.content, np.uint8)
            
            # Decode images
            source = cv2.imdecode(header_array, cv2.IMREAD_COLOR)
            template = cv2.imdecode(template_array, cv2.IMREAD_COLOR)
            
            if source is None or template is None:
                raise ValueError("Failed to read source or template image")
            
            # Get dimensions
            source_height = source.shape[0]
            template_height = template.shape[0]
            template_width = template.shape[1]
            
            # Calculate header heights
            header_height = int(source_height * header_proportion)
            template_header_height = int(template_height * header_proportion)
            
            # Extract and resize header
            header = source[0:header_height, :]
            header_aspect_ratio = header.shape[1] / header.shape[0]
            new_header_width = int(template_header_height * header_aspect_ratio)
            header_resized = cv2.resize(header, (new_header_width, template_header_height))
            
            # Create result image
            result = template.copy()
            
            # Center the header
            x_offset = (template_width - new_header_width) // 2
            
            # Handle wide headers
            if new_header_width > template_width:
                crop_start = (new_header_width - template_width) // 2
                header_resized = header_resized[:, crop_start:crop_start + template_width]
                x_offset = 0
            
            # Create header region with white background
            header_region = np.full((template_header_height, template_width, 3), 255, dtype=np.uint8)
            
            # Place header in center
            if x_offset >= 0:
                header_region[:, x_offset:x_offset + header_resized.shape[1]] = header_resized
            
            # Copy header to template
            result[0:template_header_height, :] = header_region
            
            # Save to temporary file
            temp_path = os.path.join('temp_images', f'merged_menu_{int(time.time() * 1000)}.png')
            os.makedirs('temp_images', exist_ok=True)
            
            # Save merged image
            success = cv2.imwrite(temp_path, result)
            if not success:
                raise ValueError("Failed to save merged image")
            
            # Upload to storage
            with open(temp_path, 'rb') as f:
                file_path = f"previews/merged_{int(time.time() * 1000)}.png"
                self.storage.from_(self.template_bucket).upload(
                    path=file_path,
                    file=f,
                    file_options={"content-type": "image/png"}
                )
            
            # Get public URL
            public_url = self.storage.from_(self.template_bucket).get_public_url(file_path)
            
            # Clean up temporary file
            os.remove(temp_path)
            
            return public_url
            
        except Exception as e:
            get_logger().log_activity(
                action="Template Merge Failed",
                details=str(e),
                status="error"
            )
            return None 

    def extract_dates_from_image(self, image_path: str) -> Optional[Dict[str, str]]:
        """Extract dates from the image using OCR"""
        try:
            # Open image
            with Image.open(image_path) as img:
                # Perform OCR with custom config
                text = perform_ocr(img, config='--psm 6 --oem 1')
                
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
                
                logger.info(f"Extracted dates: {dates}")
                return dates if dates else None
                
        except Exception as e:
            logger.error(f"Error extracting dates: {str(e)}")
            return None 