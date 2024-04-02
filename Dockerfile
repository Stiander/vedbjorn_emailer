FROM python:3.10-slim-buster
ENV PYTHONUNBUFFERED 1
ENV GOOGLE_APPLICATION_CREDENTIALS=vedbjorn-bb6b49fad2e3.json
RUN mkdir -p /home/emailer/
COPY ./requirements.txt /home/emailer/
RUN pip install -r /home/emailer/requirements.txt
COPY ./src/ /home/emailer/
WORKDIR /home/emailer
EXPOSE 1234
CMD python3 main.py
