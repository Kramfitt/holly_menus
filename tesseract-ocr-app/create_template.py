from PIL import Image, ImageDraw
import os

def create_template():
    # Create a new image with white background
    width = 800
    height = 1000
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    
    # Draw some guide lines
    for y in range(0, height, 100):
        draw.line([(0, y), (width, y)], fill='lightgray', width=1)
    
    # Save the template
    os.makedirs('templates', exist_ok=True)
    image.save('templates/template.png')
    print("Created template at templates/template.png")

if __name__ == '__main__':
    create_template() 