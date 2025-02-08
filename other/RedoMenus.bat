from PIL import Image
import os

def merge_menu_headers(old_menu_path, new_menu_path, output_path, header_height=360, shift_x=0):
    """
    Replace the header of an old menu with the header from a new menu.

    Args:
        old_menu_path (str): Path to the old menu image.
        new_menu_path (str): Path to the new menu image.
        output_path (str): Path to save the final combined menu.
        header_height (int): Height of the header to crop from the new menu.
        shift_x (int): Horizontal shift for fine-tuning header placement.
    """
    try:
        # Open images
        old_menu = Image.open(old_menu_path)
        new_menu = Image.open(new_menu_path)

        # Rotate old menu to correct orientation (if upside down)
        old_menu = old_menu.rotate(180, expand=True)

        # Crop the header from the new menu
        header_region = (0, 0, new_menu.width, header_height)
        new_header = new_menu.crop(header_region)

        # Overlay the new header onto the old menu
        combined_menu = old_menu.copy()
        combined_menu.paste(new_header, (shift_x, 0))

        # Save the final combined image
        combined_menu.save(output_path)
        print(f"Successfully saved combined menu to {output_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

# Logging function for improved feedback
def log_message(message):
    """Logs a message to the console with consistent formatting."""
    print(f"[LOG]: {message}")

if __name__ == "__main__":
    # Directory containing menus
    input_directory = "./menus"
    output_directory = "./processed_menus"

    # Ensure the output directory exists
    os.makedirs(output_directory, exist_ok=True)

    # Process all old and new menus in pairs
    log_message("Starting batch processing of menus...")
    for filename in os.listdir(input_directory):
        if "old" in filename.lower():  # Identify old menus
            base_name = filename.split("_old")[0]
            old_menu_path = os.path.join(input_directory, filename)
            new_menu_path = os.path.join(input_directory, f"{base_name}_new.png")  # Matching new menu filename
            output_path = os.path.join(output_directory, f"{base_name}_combined.png")

            if os.path.exists(new_menu_path):
                try:
                    merge_menu_headers(old_menu_path, new_menu_path, output_path, header_height=360, shift_x=-10)
                    log_message(f"Processed: {output_path}")
                except Exception as e:
                    log_message(f"Failed to process {filename}: {e}")
            else:
                log_message(f"Matching new menu not found for: {filename}")

    log_message("Batch processing completed.")
