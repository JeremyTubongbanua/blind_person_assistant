import depthai as dai
import cv2
import numpy as np

pipeline = dai.Pipeline()

cameraRGB = pipeline.createColorCamera()
cameraRGB.setPreviewSize(300, 300)
cameraRGB.setInterleaved(False)

xLinkOutCameraRGB = pipeline.createXLinkOut()
xLinkOutCameraRGB.setStreamName("cameraRGB")
cameraRGB.preview.link(xLinkOutCameraRGB.input)