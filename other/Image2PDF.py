from PIL import Image

def images_to_pdf(image_folder, output_pdf_path):
    """
    Combine images into a single PDF.

    Args:
        image_folder (str): Folder containing images.
        output_pdf_path (str): Path to save the output PDF.
    """
    images = []
    for filename in sorted(os.listdir(image_folder)):
        if filename.endswith(".png"):
            img_path = os.path.join(image_folder, filename)
            img = Image.open(img_path).convert("RGB")
            images.append(img)

    if images:
        images[0].save(output_pdf_path, save_all=True, append_images=images[1:])
        print(f"PDF saved to: {output_pdf_path}")

# Example usage
images_to_pdf("./output_images", "Combined_Menu.pdf")
