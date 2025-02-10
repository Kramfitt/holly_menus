from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
import os

def create_font(size):
    """Helper function to create font with fallbacks"""
    try:
        # Windows path
        return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)
    except:
        try:
            # Linux path
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except:
            try:
                # macOS path
                return ImageFont.truetype("/Library/Fonts/Arial Bold.ttf", size)
            except:
                print(f"⚠️ Using default font at size {size}")
                return ImageFont.load_default()

def test_menu_preview(image_path, start_date):
    print("Starting preview generation...")
    
    # Open test image
    img = Image.open(image_path)
    
    # Create three test images with different font sizes
    font_sizes = [25, 30, 35]  # Keep same sizes
    
    for i, font_size in enumerate(font_sizes, 1):
        print(f"\nGenerating test {i} with font size {font_size}")
        
        # Create a copy of the image
        test_img = img.copy()
        draw = ImageDraw.Draw(test_img)
        
        # Create font for this test
        font = create_font(font_size)
        
        # Position settings - moved up and left
        x_start = 320  # Moved left from 350
        y_start = 200  # Keep higher position
        x_spacing = 280
        
        # Add dates
        for day in range(7):
            x = x_start + (x_spacing * day)
            y = y_start
            current_date = start_date + timedelta(days=day)
            date_text = current_date.strftime('%a %d\n%b')
            
            # Get text size for background
            bbox = draw.textbbox((x, y), date_text, font=font)
            padding_x = 20
            padding_y = 15
            
            # Calculate box dimensions
            box_width = bbox[2] - bbox[0] + (padding_x * 2)
            box_height = (bbox[3] - bbox[1] + (padding_y * 2)) * 0.8
            
            # Draw background
            draw.rectangle([
                bbox[0] - padding_x,
                bbox[1] - padding_y,
                bbox[0] + box_width - padding_x,
                bbox[1] + box_height - padding_y
            ], fill='white')
            
            # Draw text
            draw.text((x, y), date_text, fill='black', font=font)
            print(f"Drew date {day+1} with font size {font_size}")
        
        # Save this version
        output_path = os.path.join(os.path.dirname(__file__), f'test_menu_position_{i}.png')
        test_img.save(output_path)
        print(f"Saved test {i} to: {output_path}")

if __name__ == "__main__":
    # Test image path
    image_path = r"C:\AlphaFiles\other\output_images\week3_finish.png"
    start_date = datetime.now()
    
    print("\n🚀 Starting menu preview test")
    test_menu_preview(image_path, start_date)
    print("\n✅ Test completed!") 