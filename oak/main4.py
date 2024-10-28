import depthai
# https://www.youtube.com/watch?v=e_uPEE_zlDo&t=681s
import cv2
import numpy

pipeline = depthai.Pipeline()

leftMonoCamera = pipeline.createMonoCamera()
leftMonoCamera.setBoardSocket(depthai.CameraBoardSocket.LEFT)

rightMonoCamera = pipeline.createMonoCamera()
rightMonoCamera.setBoardSocket(depthai.CameraBoardSocket.RIGHT)

xLinkOutLeft = pipeline.createXLinkOut()
xLinkOutLeft.setStreamName("leftMonoCamera")

xLinkOutRight = pipeline.createXLinkOut()
xLinkOutRight.setStreamName("rightMonoCamera")

leftMonoCamera.out.link(xLinkOutLeft.input)
rightMonoCamera.out.link(xLinkOutRight.input)

with depthai.Device(pipeline) as device:
	queueLeft = device.getOutputQueue("leftMonoCamera")
	queueRight = device.getOutputQueue("rightMonoCamera")
    
	showSideBySide = True

	while True:
		frameLeft = queueLeft.get().getCvFrame()
		frameRight = queueRight.get().getCvFrame()


		print(frameLeft)

		if showSideBySide:
			frame = numpy.hstack((frameLeft, frameRight))
		else:
			frame = numpy.uint8(frameLeft/2 + frameRight/2)

		cv2.imshow("image", frame)
		
		key = cv2.waitKey(1)
		if key == ord('q'):
			break
		if key == ord('t'):
		    showSideBySide = not showSideBySide