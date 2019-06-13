import os
import slack


def send_message(channel, message):
    slack_bot_token = os.environ['SLACK_BOT_TOKEN']
    slack_client = slack.WebClient(token=slack_bot_token)

    slack_client.chat_postMessage(channel=channel, text=message, as_user=True)
