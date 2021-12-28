FROM python:3.10.1-alpine

WORKDIR /usr/src

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app app

ENV SLACK_BOT_TOKEN=''
ENV GDOCS_SERVICE_ACCOUNT_FILENAME=''
ENV AWS_ACCESS_KEY_ID=''
ENV AWS_SECRET_ACCESS_KEY=''

USER 1000:1000

ENTRYPOINT [ "python", "-m", "app.nagbot" ]
CMD [ ]
