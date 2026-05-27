.PHONY: start stop restart install ip

start:
	python app.py

stop:
	pkill -f "python app.py" || true
	lsof -ti :5001 | xargs kill -9 2>/dev/null || true

restart:
	pkill -f "python app.py" || true
	lsof -ti :5001 | xargs kill -9 2>/dev/null || true
	sleep 1
	python app.py

install:
	pip install -r requirements.txt

ip:
	@echo "Local:   http://127.0.0.1:5001"
	@echo "Network: http://$$(ipconfig getifaddr en0 || ipconfig getifaddr en1):5001"
