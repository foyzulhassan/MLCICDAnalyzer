#!/bin/bash

python3 /home/rchavan/ci_tool/test-projects/yolov5/benchmarks.py --data coco128.yaml --weights yolov5n.pt --img 320 --hard-fail 0.29

python3 /home/rchavan/ci_tool/test-projects/yolov5/benchmarks.py --data coco128-seg.yaml --weights yolov5n-seg.pt --img 320 --hard-fail 0.22

python3 /home/rchavan/ci_tool/test-projects/yolov5/export.py --weights yolov5n-cls.pt --include onnx --img 224

python3 /home/rchavan/ci_tool/test-projects/yolov5/detect.py --weights yolov5n.onnx --img 320

python3 /home/rchavan/ci_tool/test-projects/yolov5/segment/predict.py --weights yolov5n-seg.onnx --img 320

python3 /home/rchavan/ci_tool/test-projects/yolov5/classify/predict.py --weights yolov5n-cls.onnx --img 224
