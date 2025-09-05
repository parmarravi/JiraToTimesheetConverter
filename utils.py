import os
import json
import uuid
from datetime import datetime, timedelta
import shutil
import pandas as pd

TEMP_DIR = 'temp_data'

def reset_temp_directory():
    """
    Completely removes and recreates the temp_data directory.
    Used when resetting the application or starting fresh.
    """
    try:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR)
        print(f"Successfully reset {TEMP_DIR} directory")
    except Exception as e:
        print(f"Error resetting temp directory: {str(e)}")

def ensure_temp_dir():
    """Ensure temporary directory exists"""
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

def cleanup_old_files():
    """Remove files older than 1 hour.
    Handles all temporary files including:
    - JSON data files
    - Uploaded images (logo files)
    - Any other temporary files in the directory
    """
    ensure_temp_dir()
    current_time = datetime.now()
    cleaned_count = {"images": 0, "json": 0, "other": 0}

    try:
        for filename in os.listdir(TEMP_DIR):
            filepath = os.path.join(TEMP_DIR, filename)
            file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            # Check if file is older than 1 hour
            if current_time - file_modified > timedelta(hours=1):
                try:
                    if os.path.isfile(filepath):
                        # Categorize the file type
                        if filename.startswith('logo_'):
                            cleaned_count["images"] += 1
                        elif filename.endswith('.json'):
                            cleaned_count["json"] += 1
                        else:
                            cleaned_count["other"] += 1
                        
                        os.remove(filepath)
                    elif os.path.isdir(filepath):
                        shutil.rmtree(filepath)
                        cleaned_count["other"] += 1
                except (OSError, IOError) as e:
                    print(f"Error cleaning up file {filename}: {str(e)}")

        print(f"Cleanup completed: Removed {cleaned_count['images']} images, "
              f"{cleaned_count['json']} JSON files, and {cleaned_count['other']} other files")
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")

def save_dataframe(df):
    """Save DataFrame to temporary file and return ID"""
    ensure_temp_dir()
    cleanup_old_files()
    
    file_id = str(uuid.uuid4())
    file_path = os.path.join(TEMP_DIR, f"{file_id}.json")
    
    # Save to JSON
    df.to_json(file_path)
    return file_id

def load_dataframe(file_id):
    """Load DataFrame from temporary file"""
    import pandas as pd
    
    file_path = os.path.join(TEMP_DIR, f"{file_id}.json")
    if not os.path.exists(file_path):
        return None
        
    return pd.read_json(file_path)

def remove_dataframe(file_id):
    """Remove temporary DataFrame file and its associated logo file"""
    if not file_id:
        return

    # Remove JSON data file
    file_path = os.path.join(TEMP_DIR, f"{file_id}.json")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            print(f"Error removing data file: {str(e)}")

    # Remove only the logo file associated with this session
    try:
        # Look for any file that starts with logo_{file_id}
        for filename in os.listdir(TEMP_DIR):
            if filename.startswith(f"logo_{file_id}"):
                logo_path = os.path.join(TEMP_DIR, filename)
                if os.path.exists(logo_path):
                    os.remove(logo_path)
                break  # Found and removed the associated logo file
    except OSError as e:
        print(f"Error cleaning up logo file: {str(e)}")

def get_temp_dir():
    """Get the temporary directory path, ensuring it exists"""
    ensure_temp_dir()
    return os.path.abspath(TEMP_DIR)

def should_run_cleanup():
    """Check if cleanup should be run (more than 1 hour since last cleanup)"""
    cleanup_marker = os.path.join(TEMP_DIR, '.last_cleanup')
    
    if not os.path.exists(cleanup_marker):
        return True
        
    try:
        with open(cleanup_marker, 'r') as f:
            last_cleanup_str = f.read().strip()
            last_cleanup = datetime.fromisoformat(last_cleanup_str)
            
        return datetime.now() - last_cleanup > timedelta(hours=1)
    except (ValueError, IOError) as e:
        # If there's any error reading the file, assume we should run cleanup
        print(f"Error checking cleanup time: {str(e)}")
        return True

def mark_cleanup_complete():
    """Mark that cleanup has been completed"""
    cleanup_marker = os.path.join(TEMP_DIR, '.last_cleanup')
    ensure_temp_dir()
    
    try:
        with open(cleanup_marker, 'w') as f:
            f.write(datetime.now().isoformat())
    except IOError as e:
        print(f"Error marking cleanup complete: {str(e)}")
        # Not critical if we fail to mark completion
        # Worst case: we'll try cleanup again on next request
