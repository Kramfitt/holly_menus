import pytest
from datetime import datetime, timedelta
from app.services.menu_service import MenuService

@pytest.fixture
def menu_service(mock_db, mock_storage):
    return MenuService(db=mock_db, storage=mock_storage)

def test_calculate_next_menu(menu_service):
    """Test menu calculation logic"""
    # Setup test data
    today = datetime.now().date()
    
    # Test calculation
    result = menu_service.calculate_next_menu()
    
    # Verify results
    assert result is not None
    assert result['success'] is True
    assert result['error'] is None
    
    # Check the data structure
    menu_data = result['data']
    assert 'send_date' in menu_data
    assert 'period_start' in menu_data
    assert 'season' in menu_data
    assert 'week' in menu_data

def test_season_change(menu_service, mock_db):
    """Test season change logic"""
    today = datetime.now().date()
    menu_date = today + timedelta(days=14)  # The actual date the menu is for
    change_date = menu_date + timedelta(days=1)  # Change happens after menu date
    
    # Set summer season with future change date
    mock_db.set_mock_data('summer', change_date.strftime('%Y-%m-%d'))
    
    # Test before change
    result = menu_service.calculate_next_menu()
    assert result['data']['season'] == 'summer', (
        f"Should be summer: menu date {menu_date} is before change date {change_date}"
    )
    
    # Set summer season with past change date
    change_date = menu_date - timedelta(days=1)  # Change happens before menu date
    mock_db.set_mock_data('summer', change_date.strftime('%Y-%m-%d'))
    
    # Test after change
    result = menu_service.calculate_next_menu()
    assert result['data']['season'] == 'winter', (
        f"Should be winter: menu date {menu_date} is after change date {change_date}"
    ) 