#!/usr/bin/env python3

import pathlib
import argparse
import depthai

NN_PATH_DEFAULT = pathlib.Path(__file__).parent / "models/mobilenet-ssd_openvino_2021.4_6shave.blob"

labelMap = ["person"]


parser = argparse.ArgumentParser()
parser.add_argument('nnPath', nargs='?', help="Path to mobilenet detection network blob", default=NN_PATH_DEFAULT)

args = parser.parse_args()

pipeline = depthai.Pipeline()

