import os

import slack


def send_message(channel, message):
    """ Send a message to a Slack channel
    """
    slack_client = get_client()
    slack_client.chat_postMessage(channel=channel, text=message, as_user=True)


def lookup_user_by_email(email):
    """ Look up a user by email
    :param email: an email address
    :return: If the user was identified, the ID of the user in such a way that Slack will render it as a "@user" tag.
             If the user could not be identified, the email will be return as-is.
    """
    # noinspection PyBroadException
    try:
        slack_client = get_client()
        result = slack_client.users_lookupByEmail(email=email)
        user_id = result.data['user']['id']  # Looks like: UJ0JNCX19, tag the user in a message like <@UJ0JNCX19>
        return '<@' + user_id + '>'
    except Exception:
        return email


def get_client():
    slack_bot_token = os.environ['SLACK_BOT_TOKEN']
    return slack.WebClient(token=slack_bot_token)
