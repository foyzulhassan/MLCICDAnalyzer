# export PYTHONPATH="$PWD"  # to run '$ python *.py' files in subdirectories
m=yolov5n  # official weights
b=runs/train/exp/weights/best  # best.pt checkpoint
python3 train.py --imgsz 64 --batch 32 --weights $m.pt --cfg $m.yaml --epochs 1 --device cpu  # train
for d in cpu; do  # devices
    for w in $m $b; do  # weights
        python3 val.py --imgsz 64 --batch 32 --weights $w.pt --device $d  # val
        python3 detect.py --imgsz 64 --weights $w.pt --device $d  # detect
    done
done
python3 hubconf.py --model $m  # hub
# python3 models/tf.py --weights $m.pt  # build TF model
python3 models/yolo.py --cfg $m.yaml  # build PyTorch model
python3 export.py --weights $m.pt --img 64 --include torchscript  # export
python3 - <<EOF
import torch
im = torch.zeros([1, 3, 64, 64])
for path in '$m', '$b':
    model = torch.hub.load('.', 'custom', path=path, source='local')
    print(model('data/images/bus.jpg'))
    model(im)  # warmup, build grids for trace
    torch.jit.trace(model, [im])
EOF

m=yolov5n-seg  # official weights
b=runs/train-seg/exp/weights/best  # best.pt checkpoint
python3 segment/train.py --imgsz 64 --batch 32 --weights $m.pt --cfg $m.yaml --epochs 1 --device cpu  # train
python3 segment/train.py --imgsz 64 --batch 32 --weights '' --cfg $m.yaml --epochs 1 --device cpu  # train
for d in cpu; do  # devices
    for w in $m $b; do  # weights
        python3 segment/val.py --imgsz 64 --batch 32 --weights $w.pt --device $d  # val
        python3 segment/predict.py --imgsz 64 --weights $w.pt --device $d  # predict
        python3 export.py --weights $w.pt --img 64 --include torchscript --device $d  # export
    done
done

m=yolov5n-cls.pt  # official weights
b=runs/train-cls/exp/weights/best.pt  # best.pt checkpoint
python3 classify/train.py --imgsz 32 --model $m --data mnist160 --epochs 1  # train
python3 classify/val.py --imgsz 32 --weights $b --data ../datasets/mnist160  # val
python3 classify/predict.py --imgsz 32 --weights $b --source ../datasets/mnist160/test/7/60.png  # predict
python3 classify/predict.py --imgsz 32 --weights $m --source data/images/bus.jpg  # predict
python3 export.py --weights $b --img 64 --include torchscript  # export
python3 - <<EOF
import torch
for path in '$m', '$b':
    model = torch.hub.load('.', 'custom', path=path, source='local')
EOF