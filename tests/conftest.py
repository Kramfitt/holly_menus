import pytest
from unittest.mock import MagicMock
from datetime import datetime

@pytest.fixture
def mock_db():
    """Mock database for testing"""
    db = MagicMock()
    
    # Create a fresh mock for each test
    def get_mock_data(season='summer', change_date=None):
        return [{
            'season': season,
            'start_date': '2024-01-01',
            'season_change_date': change_date or '2024-06-01',
            'days_in_advance': 14,
            'recipient_emails': ['test@example.com']
        }]
    
    # Setup the mock with default data
    db.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = get_mock_data()
    
    # Add helper method to update mock data
    db.set_mock_data = lambda season, change_date: setattr(
        db.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value,
        'data',
        get_mock_data(season, change_date)
    )
    
    return db

@pytest.fixture
def mock_storage():
    """Mock storage for testing"""
    storage = MagicMock()
    return storage 