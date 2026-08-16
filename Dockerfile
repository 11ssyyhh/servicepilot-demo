FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN python -m compileall -q .

EXPOSE 8001

CMD ["python", "main.py", "1"]
