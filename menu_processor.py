import re
from datetime import datetime
import logging

def detect_season_and_week(text):
    """
    Detect season and week number from menu text with enhanced pattern matching.
    Handles formats like "Summer Menu Week 1" and filenames like "SummerWeek1"
    """
    # Convert text to lowercase for case-insensitive matching
    text_lower = text.lower()
    
    # Season detection - look for summer/winter in text
    season = None
    if 'summer' in text_lower:
        season = 'Summer'
    elif 'winter' in text_lower:
        season = 'Winter'
    else:
        # Default to season based on current month (Southern Hemisphere)
        current_month = datetime.now().month
        if current_month in [12, 1, 2, 3, 4]:
            season = 'Summer'
        else:
            season = 'Winter'
    
    # Week detection patterns - ordered by preference
    week_patterns = [
        r'(?:summer|winter)\s*menu\s*week\s*(\d+)',  # "Summer Menu Week 1"
        r'(?:summer|winter)\s*week\s*(\d+)',         # "Summer Week 1"
        r'(?:summer|winter)week(\d+)',               # "SummerWeek1"
        r'menu\s*week\s*(\d+)',                      # "Menu Week 1"
        r'week\s*(\d+)',                             # "Week 1"
        r'wk\.?\s*(\d+)',                            # "Wk 1", "Wk.1"
    ]
    
    week = None
    for pattern in week_patterns:
        match = re.search(pattern, text_lower)
        if match:
            week = int(match.group(1))
            if 1 <= week <= 5:  # Validate week number is in expected range
                break
    
    # If no pattern matches, look for any standalone digit 1-5
    if week is None:
        numbers = re.findall(r'\b[1-5]\b', text)
        if len(numbers) == 1:  # Only use if we find exactly one valid number
            week = int(numbers[0])
    
    if season and week:
        logging.info(f"Successfully detected {season} Week {week}")
    else:
        logging.warning(f"Incomplete detection - Season: {season}, Week: {week}")
        # Log the text for debugging
        logging.info(f"Text analyzed:\n{text}")
    
    return season, week 