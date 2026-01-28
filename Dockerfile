FROM python:3.13-alpine
WORKDIR /bot
COPY requirements.txt /bot/
COPY .env /bot/
RUN pip install -r requirements.txt
COPY . /bot
CMD python main.py
