import os

# Define directories
images_dir = '/Users/jeremytubongbanua/GitHub/blind_person_assistant/dataset/images/'
labels_dir = '/Users/jeremytubongbanua/GitHub/blind_person_assistant/dataset/labels/'
classes_file = '/Users/jeremytubongbanua/GitHub/blind_person_assistant/dataset/classes.txt'

# Get the number of lines in classes.txt
with open(classes_file, 'r') as f:
    num_classes = len(f.readlines())

# Get list of image files
image_files = [f for f in os.listdir(images_dir) if f.endswith('.jpg') or f.endswith('.png')]

# Check each image file
for image_file in image_files:
    base_name = os.path.splitext(image_file)[0]
    label_file = os.path.join(labels_dir, base_name + '.txt')
    
    if not os.path.exists(label_file):
        print(f"Label file missing for image: {image_file}")
        continue
    
    with open(label_file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            label_index = int(line.split()[0])
            if label_index >= num_classes:
                print(f"Invalid label index {label_index} in file: {label_file}")

print("Check completed.")