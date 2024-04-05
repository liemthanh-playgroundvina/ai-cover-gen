# AI COVER GEN Using RVC V2
- Link: https://github.com/SociallyIneptWeeb/AICoverGen

- Queue System using celery(python) + redis + rabbitMQ
- Image information: Ubuntu 20.04 + CUDA 11.8 + CUDnn 8. + ONNX runtime + Python 3.9

1. Clone & download model
```# command
git clone https://github.com/liemthanh-playgroundvina/ai-cover-gen
cd ai-cover
make download_model
```

2. Build Image
```# command
make build
```
3. Start
```# command
make start
```