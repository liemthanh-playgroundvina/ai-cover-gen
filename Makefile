start-local:
	cd src && bash -c "celery -A ai_celery.router worker -Q ai_cover_gen --logfile=logs/celery.log && tail -f /dev/null" &

cmd-image:
	docker run -it --gpus all --rm ai-cover-gen /bin/bash

download_model:
	python src/download_models.py

# Docker
build:
	docker build -t ai-cover-gen -f Dockerfile .

start:
	docker compose -f docker-compose.yml down
	docker compose -f docker-compose.yml up -d

stop:
	docker compose -f docker-compose.yml down

cmd-app:
	docker compose exec app /bin/bash

# check:
# 	import torch
# 	print(torch.__version__)
# 	print(torch.version.cuda)
# 	import torch
# 	print(torch.backends.cudnn.version())
# 	find / -name "" 2>/dev/null

