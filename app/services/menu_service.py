from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import time
import os
from werkzeug.utils import secure_filename
import traceback

from app.utils.logger import get_logger

class MenuService:
    def __init__(self, db, storage):
        self.db = db
        self.storage = storage
        self.bucket = 'menu-templates'
        self._ensure_bucket_exists()
        
    def _ensure_bucket_exists(self):
        """Ensure the storage bucket exists"""
        try:
            # Try to get bucket info
            buckets = self.storage.list_buckets()
            bucket_exists = any(b['name'] == self.bucket for b in buckets)
            
            if not bucket_exists:
                try:
                    # Create the bucket with minimal config
                    self.storage.create_bucket(self.bucket)
                    
                    get_logger().log_activity(
                        action="Bucket Created",
                        details=f"Created storage bucket: {self.bucket}",
                        status="success"
                    )
                    
                    # Wait a moment for bucket to be ready
                    time.sleep(1)
                    
                except Exception as bucket_error:
                    # Log but don't fail - bucket might exist but be inaccessible
                    get_logger().log_activity(
                        action="Bucket Creation Note",
                        details=str(bucket_error),
                        status="info"
                    )
                
            return True
            
        except Exception as e:
            get_logger().log_activity(
                action="Bucket Check Failed",
                details=str(e),
                status="error"
            )
            return False
    
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
                print("No menu settings found")
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

            return {
                'send_date': send_date,
                'period_start': next_period_start,
                'season': season,
                'menu_pair': week_pair
            }

        except Exception as e:
            print(f"Error calculating next menu: {str(e)}")
            return None
    
    def get_settings(self) -> Optional[Dict[str, Any]]:
        """Get current menu settings"""
        try:
            response = self.db.table('menu_settings')\
                .select('*')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
                
            if not response.data:
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
                
            return settings
            
        except Exception as e:
            print(f"Error getting settings: {str(e)}")
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

    def save_template(self, file, season, week):
        """Save menu template to storage and database"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Validate file first
                self._validate_file(file)
                
                # Ensure bucket exists
                if not self._ensure_bucket_exists():
                    raise ValueError("Failed to create or access storage bucket")
                
                # Clean up old template
                self._cleanup_old_template(season, week)
                
                # Generate unique filename
                filename = secure_filename(f"{season.lower()}_week{week}_{int(time.time())}{os.path.splitext(file.filename)[1]}")
                file_path = f"{season}/{filename}"
                
                # Read file content
                file_content = file.read()
                file.seek(0)
                
                # Upload to storage
                self.storage.from_(self.bucket).upload(
                    file_path,
                    file_content,
                    {'content-type': file.content_type}
                )
                
                # Get public URL
                file_url = self.storage.from_(self.bucket).get_public_url(file_path)
                
                # Save to database
                self.db.table('menu_templates').upsert({
                    'season': season.lower(),
                    'week': int(week),
                    'file_path': file_path,
                    'file_url': file_url,
                    'file_type': file.content_type,
                    'file_size': len(file_content),
                    'updated_at': datetime.now().isoformat()
                }).execute()
                
                get_logger().log_activity(
                    action="Template Upload",
                    details={
                        'season': season,
                        'week': week,
                        'file_type': file.content_type,
                        'file_size': len(file_content),
                        'path': file_path
                    },
                    status="success"
                )
                
                return {'success': True, 'url': file_url}
                
            except ValueError as e:
                # Don't retry validation errors
                get_logger().log_activity(
                    action="Template Upload Failed",
                    details=str(e),
                    status="error"
                )
                return {'error': str(e)}
                
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    get_logger().log_activity(
                        action="Template Upload Failed",
                        details=f"Failed after {max_retries} attempts: {str(e)}",
                        status="error"
                    )
                    return {'error': str(e)}
                
                time.sleep(1)
                get_logger().log_activity(
                    action="Template Upload Retry",
                    details=f"Attempt {retry_count} of {max_retries}",
                    status="warning"
                )

    def get_templates(self):
        """Get all templates organized by season"""
        try:
            response = self.db.table('menu_templates').select('*').execute()
            templates = {'summer': {}, 'winter': {}}
            
            for template in response.data:
                season = template['season']
                week = str(template['week'])
                templates[season][week] = {
                    'file_url': template.get('file_url'),
                    'updated_at': template['updated_at']
                }
            
            return templates
        except Exception as e:
            get_logger().log_activity(
                action="Template Fetch Failed",
                details=str(e),
                status="error"
            )
            return {'summer': {}, 'winter': {}}

    def get_template(self, season, week):
        """Get a specific template"""
        try:
            response = self.db.table('menu_templates')\
                .select('*')\
                .eq('season', season.lower())\
                .eq('week', int(week))\
                .execute()
                
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
        """Generate a preview of the menu template"""
        try:
            # Input validation
            if not template:
                raise ValueError("Template is required")
            
            if not start_date:
                raise ValueError("Start date is required")
            
            if not isinstance(start_date, datetime):
                raise ValueError("Invalid start date format")
            
            # Required template fields
            required_fields = ['season', 'week', 'file_url']
            missing = [f for f in required_fields if not template.get(f)]
            if missing:
                raise ValueError(f"Missing template fields: {', '.join(missing)}")
            
            # Validate URL
            file_url = template.get('file_url')
            if not file_url or not file_url.startswith('http'):
                raise ValueError("Invalid template URL")
            
            # Format dates
            try:
                period_end = start_date + timedelta(days=13)  # 2 weeks
                date_range = f"{start_date.strftime('%d %b')} - {period_end.strftime('%d %b %Y')}"
            except Exception as e:
                raise ValueError(f"Error formatting dates: {str(e)}")
            
            # Create preview data
            preview_data = {
                'success': True,
                'template': {
                    'url': file_url,
                    'season': template['season'].title(),
                    'week': template['week'],
                    'date_range': date_range,
                    'period_start': start_date.strftime('%Y-%m-%d'),
                    'period_end': period_end.strftime('%Y-%m-%d')
                }
            }
            
            # Log success
            get_logger().log_activity(
                action="Preview Generated",
                details={
                    'season': template['season'],
                    'week': template['week'],
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'success': True
                },
                status="success"
            )
            
            return preview_data
            
        except ValueError as e:
            # Log validation errors
            get_logger().log_activity(
                action="Preview Validation Failed",
                details=str(e),
                status="warning"
            )
            raise
            
        except Exception as e:
            # Log unexpected errors
            get_logger().log_activity(
                action="Preview Generation Failed",
                details={
                    'error': str(e),
                    'traceback': traceback.format_exc()
                },
                status="error"
            )
            raise ValueError(f"Failed to generate preview: {str(e)}")

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
                
            except Exception as e:
                raise ValueError(f"File content validation failed: {str(e)}")
            
            return True
            
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
                
                # Then delete
                try:
                    self.storage.from_(self.bucket).remove([old_template['file_path']])
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
            
            # Create backup path
            backup_path = f"backup/{template['season']}/{os.path.basename(template['file_path'])}"
            
            # Copy file to backup
            content = self.storage.from_(self.bucket).download(template['file_path'])
            self.storage.from_(self.bucket).upload(
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