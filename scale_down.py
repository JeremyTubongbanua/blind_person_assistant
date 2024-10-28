from PIL import Image, ExifTags
import os

def scale_down_images(directory, max_size=(1000, 1000)):
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            filepath = os.path.join(directory, filename)
            with Image.open(filepath) as img:
                # Check if the image has EXIF orientation data and reset it if present
                try:
                    for orientation in ExifTags.TAGS.keys():
                        if ExifTags.TAGS[orientation] == 'Orientation':
                            break
                    exif = img._getexif()
                    if exif and orientation in exif:
                        if exif[orientation] == 3:
                            img = img.rotate(180, expand=True)
                        elif exif[orientation] == 6:
                            img = img.rotate(270, expand=True)
                        elif exif[orientation] == 8:
                            img = img.rotate(90, expand=True)
                except (AttributeError, KeyError, IndexError):
                    # Cases where image has no EXIF data
                    pass
                
                # Scale down if needed
                if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                    img.thumbnail(max_size)
                    new_filename = f"reduced_{filename}"
                    new_filepath = os.path.join(directory, new_filename)
                    img.save(new_filepath)
                    print(f"Scaled down and saved: {new_filepath}")

if __name__ == "__main__":
    directory = os.path.dirname(os.path.abspath(__file__))
    scale_down_images(directory)
