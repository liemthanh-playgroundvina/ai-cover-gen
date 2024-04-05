download_model:
	python ./src/download_models.py
	curl -o ./rvc_models/ai_cover_rvc_models.zip https://aiservices-bucket.s3.ap-southeast-1.amazonaws.com/ai_model/ai-cover/ai_cover_rvc_models.zip
	unzip ./rvc_models/ai_cover_rvc_models.zip -d ./rvc_models

config:
	cp src/configs/env.example src/configs/.env
	# And add params ...

# Docker
build:
	docker pull nvidia/cuda:11.8.0-cudnn8-devel-ubuntu20.04
	docker build -t ai-cover-gen -f Dockerfile .

start:
	docker compose -f docker-compose.yml down
	docker compose -f docker-compose.yml up -d

stop:
	docker compose -f docker-compose.yml down


#cmd-image:
#	docker run -it --gpus all --rm ai-cover-gen /bin/bash
#
#cmd-app:
#	docker compose exec app /bin/bash
#
# check:
# 	import torch
# 	print(torch.__version__)
# 	print(torch.version.cuda)
# 	import torch
# 	print(torch.backends.cudnn.version())
# 	find / -name "" 2>/dev/null