import depthai

pipeline = depthai.Pipeline()

# Create nodes, configure them and link them together

# Connect to the device and upload the pipeline to it
with depthai.Device(pipeline) as device:
    # Print MxID, USB speed, and available cameras on the device
    print('MxId:',device.getDeviceInfo().getMxId())
    print('USB speed:',device.getUsbSpeed())
    print('Connected cameras:',device.getConnectedCameras())
