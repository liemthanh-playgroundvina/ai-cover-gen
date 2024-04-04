import onnxruntime as ort
import os
orts = ort.InferenceSession("mdxnet_models/UVR-MDX-NET-Voc_FT.onnx", providers=['CUDAExecutionProvider'])
print(orts._providers)
print(os.environ.get("LD_LIBRARY_PATH"))
