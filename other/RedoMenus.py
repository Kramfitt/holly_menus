from PIL import Image
import os
import argparse

def merge_menu_parts(new_header_path, old_menu_path, output_path, header_height=360, shift_x=0, shrink_factor=1.0):
    """
    Merge the header from the new menu with the content from the old menu.

    Args:
        new_header_path (str): Path to the image with the new header.
        old_menu_path (str): Path to the image with the old menu content.
        output_path (str): Path to save the final merged menu.
        header_height (int): Height of the header to crop from the new menu.
        shift_x (int): Horizontal shift for header placement.
        shrink_factor (float): Factor to shrink the header width (e.g., 0.99 for 99% of the width).
    """
    try:
        print(f"Processing: {new_header_path} (header) + {old_menu_path} (content) -> {output_path}")

        # Open the images
        new_header = Image.open(new_header_path)
        old_menu = Image.open(old_menu_path)

        # Crop the header from the new menu
        header_region = (0, 0, new_header.width, header_height)
        cropped_header = new_header.crop(header_region)

        # Shrink the header if a shrink factor is provided
        if shrink_factor < 1.0:
            new_width = int(cropped_header.width * shrink_factor)  # Shrink by factor
            print(f"Original header width: {cropped_header.width}, Shrinking to: {new_width}")
            cropped_header = cropped_header.resize((new_width, header_height), Image.Resampling.LANCZOS)
            print(f"Shrunk header width: {cropped_header.width}")

        # Resize the header width to match the old menu (only if no shrinking was applied)
        if shrink_factor == 1.0 and cropped_header.width != old_menu.width:
            print(f"Resizing header to match old menu width: {old_menu.width}")
            cropped_header = cropped_header.resize((old_menu.width, header_height), Image.Resampling.LANCZOS)

        # Create a new image combining header and content
        combined_menu = Image.new("RGB", (old_menu.width, old_menu.height))
        combined_menu.paste(cropped_header, (shift_x, 0))  # Paste the new header
        combined_menu.paste(old_menu.crop((0, header_height, old_menu.width, old_menu.height)),
                            (0, header_height))  # Paste the rest of the old menu

        # Save the final image
        combined_menu.save(output_path)
        print(f"Saved: {output_path}")
    except Exception as e:
        print(f"Error merging {new_header_path} and {old_menu_path}: {e}")

def process_menus(folder, header_height, params):
    """
    Process all new headers and old menus in the same folder to create merged menus.

    Args:
        folder (str): Path to the folder containing the images.
        header_height (int): Default height of the header to crop.
        params (dict): Per-page parameters for adjustments.
    """
    for file in os.listdir(folder):
        if "hlsnw_" in file and "_corrected.png" in file:  # Identify new headers
            base_name = file.replace("hlsnw_", "").replace("_corrected.png", "")
            new_header_path = os.path.join(folder, file)
            old_menu_path = os.path.join(folder, f"hlsow_{base_name}_corrected.png")
            output_path = os.path.join(folder, f"hlsow_{base_name}_merged.png")

            if os.path.exists(old_menu_path):
                # Apply per-page parameters
                page_params = params.get(base_name, {})
                shift_x = page_params.get("shift_x", 0)
                shrink_factor = page_params.get("shrink_factor", 1.0)
                page_header_height = page_params.get("header_height", header_height)

                merge_menu_parts(new_header_path, old_menu_path, output_path,
                                 page_header_height, shift_x, shrink_factor)
            else:
                print(f"No matching old menu found for: {file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge headers from new menus with content from old menus.")
    parser.add_argument("folder", type=str, help="Folder containing the images.")
    parser.add_argument("--header_height", type=int, default=360, help="Default height of the header to crop (default: 360px).")

    args = parser.parse_args()

    # Define per-page parameters
    page_params = {
        "page_1": {
            "shift_x": 25,        # Move header right by 10px
            "shrink_factor": 1.0  # No shrinking
        },
        "page_2": {
            "shift_x": 30,         # No horizontal shift
            "shrink_factor": 0.96 # Shrink header to 99% width
        }
    }

    # Process the menus
    process_menus(args.folder, args.header_height, page_params)
