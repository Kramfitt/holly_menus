from PIL import Image
import pytesseract

# Path to your test image
image_path = "HLSFW2.png"

# Run OCR on the image
text = pytesseract.image_to_string(Image.open(image_path))
print("Extracted Text:")
print(text)
