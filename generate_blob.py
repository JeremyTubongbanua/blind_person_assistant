import os
import sys
import shutil
from pathlib import Path

def convert_to_blob(model_path, image_size=416):
    model_path = Path(model_path)
    if not model_path.exists():
        print(f"Error: Model file not found at {model_path}")
        return False
    
    print(f"Converting {model_path} to blob format...")
    
    try:
        from ultralytics import YOLO as UltralyticsYOLO
        model = UltralyticsYOLO(model_path)
        print("Model loaded successfully")
    except Exception as e:
        print(f"Error loading model: {e}")
        return False
    
    print("Exporting to OpenVINO IR format...")
    try:
        openvino_success = model.export(format='openvino', imgsz=image_size)
        if not openvino_success:
            print("Failed to export to OpenVINO format")
            return False
        
        model_dir = model_path.parent
        openvino_dir = None
        
        potential_dir = f"{model_path.stem}_openvino_model"
        if (model_dir / potential_dir).exists():
            openvino_dir = model_dir / potential_dir
            print(f"Found OpenVINO model directory: {openvino_dir}")
        else:
            for directory in model_dir.glob("*_openvino_model*"):
                if directory.is_dir():
                    openvino_dir = directory
                    print(f"Found OpenVINO model directory: {openvino_dir}")
                    break
            
        if not openvino_dir:
            print("Could not find OpenVINO model directory")
            return False
        
        xml_files = list(openvino_dir.glob("*.xml"))
        if not xml_files:
            print(f"No XML files found in {openvino_dir}")
            return False
        
        xml_path = xml_files[0]
        blob_path = model_path.with_suffix('.blob')
        
    except Exception as e:
        print(f"Error exporting to OpenVINO: {e}")
        return False
    
    try:
        print("Installing required packages...")
        os.system(f"{sys.executable} -m pip install depthai==2.21.2")
        
        try:
            import depthai as dai
            
            print(f"Using DeviceBootloader to create blob file...")
            
            bootloader = dai.DeviceBootloader('')
            xml_path_str = str(xml_path)
            blob_path_str = str(blob_path)
            
            if '.xml' in xml_path_str:
                bin_path = xml_path_str.replace('.xml', '.bin')
                
                blob_config = {
                    'shave': 6,
                    'cmx_slices': 6,
                    'NCE_delay': 1,
                }
                
                print(f"Converting: {xml_path_str} -> {blob_path_str}")
                bootloader.compile(xml_path_str, blob_path_str, blob_config, True)
            
            if os.path.exists(blob_path_str):
                print(f"Blob successfully generated at: {blob_path_str}")
                return True
            else:
                print(f"Error: Blob file was not created at {blob_path_str}")
                
                print("\nAttempting with compile_tool command...")
                compile_tool_cmd = f"compile_tool -m {xml_path} -o {blob_path} -d MYRIAD -ip FP16"
                print(f"Running: {compile_tool_cmd}")
                os.system(compile_tool_cmd)
                
                if os.path.exists(blob_path):
                    print(f"Blob successfully generated at: {blob_path}")
                    return True
                return False
            
        except Exception as e:
            print(f"Error with DeviceBootloader method: {e}")
            
            print("\nTrying with openvino_2022.1.0...")
            os.system("apt-get update && apt-get install -y wget")
            os.system("wget -q https://storage.openvinotoolkit.org/repositories/openvino/packages/2022.1/linux/l_openvino_toolkit_ubuntu20_2022.1.0.643_x86_64.tgz")
            os.system("tar -xf l_openvino_toolkit_ubuntu20_2022.1.0.643_x86_64.tgz")
            os.system("mv l_openvino_toolkit_ubuntu20_2022.1.0.643_x86_64 /opt/intel/openvino_2022.1.0")
            
            compile_cmd = f"source /opt/intel/openvino_2022.1.0/setupvars.sh && /opt/intel/openvino_2022.1.0/deployment_tools/tools/compile_tool/compile_tool -m {xml_path} -o {blob_path} -d MYRIAD -ip FP16"
            print(f"Running: {compile_cmd}")
            os.system(compile_cmd)
            
            if os.path.exists(blob_path):
                print(f"Blob successfully generated at: {blob_path}")
                return True
                
            return False
            
    except Exception as e:
        print(f"Error during conversion: {e}")
        
        print("\nManual conversion instructions:")
        print("1. Install OpenVINO 2021.4 or 2022.1 (compatible with OAK-D)")
        print("2. Use the following command:")
        print(f"   source /opt/intel/openvino_2021/bin/setupvars.sh")
        print(f"   compile_tool -m {xml_path} -o {blob_path} -d MYRIAD -ip FP16")
        
        return False

if __name__ == "__main__":
    model_path = "yolov5_training/nano_speed/weights/best.pt"
        
    if not os.path.exists(model_path):
        print(f"Error: Model not found at {model_path}")
        sys.exit(1)
    
    img_size = 416
    
    success = convert_to_blob(model_path, img_size)
    
    if success:
        print("\nConversion completed successfully!")
        print("You can now use this blob file with the OAK-D Lite for on-device inference.")
    else:
        print("\nConversion failed. Please check the error messages above.")