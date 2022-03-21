install:
	sudo apt -y install \
		build-essential \
		python3-pip \
		sox \
		libsox-dev \
		libatlas-base-dev
	pip3 install -r requirements.txt
	sudo ln -s /home/pi/train-announcer/trainannouncer.service /etc/systemd/system/trainannouncer.service
	sudo systemctl daemon-reload
	sudo systemctl enable trainannouncer.service

tidy:
	isort ./**/*.py
	black ./**/*.py
	pylint --fail-under=9 ./**/*.py
