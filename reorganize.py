import os
import shutil
from datetime import datetime
import time

def wait_for_file_access(file_path, max_attempts=3):
    """Try to access a file multiple times with delays"""
    for attempt in range(max_attempts):
        try:
            # Try to open the file to check if it's accessible
            with open(file_path, 'r') as _:
                return True
        except PermissionError:
            if attempt < max_attempts - 1:
                print(f"File {file_path} is locked. Waiting 2 seconds...")
                time.sleep(2)
            continue
    return False

def safe_copy(src, dst):
    """Safely copy a file with multiple attempts"""
    if not os.path.exists(src):
        print(f"Warning: Source file {src} does not exist")
        return False
        
    try:
        if not wait_for_file_access(src):
            print(f"⚠️ Could not access {src} - file may be in use")
            return False
            
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print(f"✅ Copied {src} -> {dst}")
        return True
    except Exception as e:
        print(f"❌ Error copying {src}: {str(e)}")
        return False

def create_backup():
    """Create a backup of the current project"""
    backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"📦 Creating backup in {backup_dir}...")
    
    try:
        # Copy everything except the backup directory itself
        shutil.copytree('.', backup_dir, ignore=shutil.ignore_patterns(
            'backup_*', '__pycache__', '*.pyc', '.git'
        ))
        return backup_dir
    except PermissionError:
        print("⚠️ Some files are in use. Please:")
        print("1. Close VS Code")
        print("2. Close any other programs that might have project files open")
        print("3. Run this script again")
        return None

def create_directory_structure():
    """Create the new directory structure"""
    directories = [
        'app',
        'app/routes',
        'app/services',
        'app/utils',
        'worker',
        'config',
        'templates/components'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        # Create __init__.py in each Python package directory
        if 'templates' not in directory:
            init_file = os.path.join(directory, '__init__.py')
            if not os.path.exists(init_file):
                open(init_file, 'a').close()
                print(f"Created {init_file}")
        print(f"Created directory: {directory}")

def copy_files():
    """Copy files to their new locations"""
    moves = [
        # Move main app files
        ('app.py', 'app/routes/main.py'),
        
        # Move worker files
        ('worker.py', 'worker/main.py'),
        
        # Move templates
        ('templates/index.html', 'templates/index.html'),
        ('templates/base.html', 'templates/base.html'),
        ('templates/menu_management.html', 'templates/menu_management.html'),
        
        # Move utils
        ('utils/logger.py', 'app/utils/logger.py'),
        ('utils/notifications.py', 'app/utils/notifications.py'),
        ('utils/backup.py', 'app/utils/backup.py'),
    ]
    
    success = True
    for src, dst in moves:
        if not safe_copy(src, dst):
            success = False
    return success

def create_init_files():
    """Create __init__.py files"""
    init_locations = [
        'app',
        'app/routes',
        'app/services',
        'app/utils',
        'worker',
        'config'
    ]
    
    for location in init_locations:
        init_file = os.path.join(location, '__init__.py')
        if not os.path.exists(init_file):
            open(init_file, 'a').close()
            print(f"Created {init_file}")

def main():
    print("🚀 Creating project structure...")
    create_directory_structure()
    print("\n✅ Basic structure created!")
    print("\nNext steps:")
    print("1. Manually copy app.py to app/routes/main.py")
    print("2. Manually copy worker.py to worker/main.py")
    print("3. Move template files to their new locations")

if __name__ == "__main__":
    main() 