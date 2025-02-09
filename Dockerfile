FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Make it clear this is a background worker
ENV IS_WORKER=true

CMD ["python", "menu_scheduler.py"]