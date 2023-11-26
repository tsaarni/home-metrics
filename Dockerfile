FROM python:3.11-alpine
COPY . .
RUN pip3 install -r /requirements.txt
CMD ["python3", "/app/main.py", "--config", "/config/config.yaml"]
