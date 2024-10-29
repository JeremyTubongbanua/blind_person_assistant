import os

# Define the file paths
original_classes_file = "classes.txt"
new_classes_file = "new_classes.txt"
label_folder = "."

# Step 1: Read the original and new classes to create the index mapping
with open(original_classes_file, 'r') as f:
    original_classes = f.read().splitlines()

with open(new_classes_file, 'w') as f:
    # Write only the selected classes to the new_classes file
    selected_classes = ["person", "pole", "garbage_can", "door", "exit_sign", "general_sign"]
    f.write("\n".join(selected_classes) + "\n")

# Create a mapping from old class index to new class index
class_mapping = {original_classes.index(cls): idx for idx, cls in enumerate(selected_classes) if cls in original_classes}

# Step 2: Process each label file in the current directory
for filename in os.listdir(label_folder):
    if filename.endswith(".txt") and filename != original_classes_file and filename != new_classes_file:
        with open(filename, 'r') as f:
            lines = f.readlines()

        # Step 3: Rewrite each label with the new class index if it's in our mapping
        updated_lines = []
        for line in lines:
            parts = line.split()
            old_class_index = int(parts[0])

            # Only rewrite if the class index is in our selected classes
            if old_class_index in class_mapping:
                new_class_index = class_mapping[old_class_index]
                updated_line = f"{new_class_index} " + " ".join(parts[1:]) + "\n"
                updated_lines.append(updated_line)
            else:
                # Keep lines with classes not in new_classes.txt unchanged
                updated_lines.append(line)

        # Save the updated label file
        with open(filename, 'w') as f:
            f.writelines(updated_lines)

print("Labels updated successfully.")
