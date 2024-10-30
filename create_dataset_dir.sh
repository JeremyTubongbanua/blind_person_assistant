#!/bin/bash

# Create directories
mkdir -p dataset/images/train dataset/labels/train
mkdir -p dataset/images/test dataset/labels/test

# Copy classes.txt
cp labeled/classes.txt dataset/

# Get the list of JPG files
files=(labeled/*.JPG)
total_files=${#files[@]}
train_count=$((total_files * 80 / 100))

# Shuffle the files
shuffled_files=($(shuf -e "${files[@]}"))

# Copy 80% to train and 20% to test
for i in "${!shuffled_files[@]}"; do
    if [ "$i" -lt "$train_count" ]; then
        cp "${shuffled_files[$i]}" dataset/images/train/
        txt_file="${shuffled_files[$i]%.JPG}.txt"
        cp "$txt_file" dataset/labels/train/
    else
        cp "${shuffled_files[$i]}" dataset/images/test/
        txt_file="${shuffled_files[$i]%.JPG}.txt"
        cp "$txt_file" dataset/labels/test/
    fi
done

# Remove any classes.txt in the labels directories
rm -f dataset/labels/train/classes.txt
rm -f dataset/labels/test/classes.txt
