install:
	sudo apt -y install \
		build-essential \
		python3-pip \
		sox \
		libsox-dev \
		libatlas-base-dev
	pip3 install -r requirements.txt
	ln -s /home/pi/train-announcer/trainannouncer.service /etc/systemd/system/trainannouncer.service
	systemctl daemon-reload
	systemctl enable air.service
