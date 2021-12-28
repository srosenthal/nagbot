#/bin/bash

docker run \
  -e "SLACK_BOT_TOKEN=" \
  -e "AWS_ACCESS_KEY_ID=" \
  -e "AWS_SECRET_ACCESS_KEY=" \
  -e "GDOCS_SERVICE_ACCOUNT_FILENAME=/gdocs-service-account.json" \
  -v "$PWD/gdocs-service-account.json:/gdocs-service-account.json:ro" \
  nagbot notify -c "#nagbot-testing" --dryrun

docker run \
  -e "SLACK_BOT_TOKEN=" \
  -e "AWS_ACCESS_KEY_ID=" \
  -e "AWS_SECRET_ACCESS_KEY=" \
  -e "GDOCS_SERVICE_ACCOUNT_FILENAME=/gdocs-service-account.json" \
  -v "$PWD/gdocs-service-account.json:/gdocs-service-account.json:ro" \
  nagbot execute -c "#aws" --dryrun
