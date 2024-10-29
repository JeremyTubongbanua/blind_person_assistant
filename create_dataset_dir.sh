#!/bin/bash
mkdir -p dataset/images/train dataset/labels/train

cp labeled/*.JPG dataset/images/train
cp labeled/classes.txt dataset/
cp labeled/*.txt dataset/labels/train
rm -f dataset/labels/train/classes.txt
