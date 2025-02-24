from PIL import Image, ImageDraw, ImageFont
import os

def create_test_image():
    # Create a new image with white background
    width = 800
    height = 600
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    
    # Try to use a system font
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Read test data
    with open('templates/test_data.txt', 'r') as f:
        lines = f.readlines()
    
    # Draw each line
    y = 50
    for line in lines:
        draw.text((50, y), line.strip(), fill='black', font=font)
        y += 50
    
    # Save the image
    os.makedirs('temp_images', exist_ok=True)
    image.save('temp_images/test_menu.png')
    print("Created test image at temp_images/test_menu.png")

if __name__ == '__main__':
    create_test_image() 