import os
import unittest
from unittest.mock import patch

import app.sqslack


class TestSlack(unittest.TestCase):
    @patch('app.sqslack.slack.WebClient')
    def test_send_message(self, mock_client):
        channel = '#nagbot'
        message = 'Hey everybody!'
        token = '<not a real Slack API token>'
        os.environ['SLACK_BOT_TOKEN'] = token

        mock_slack = mock_client.return_value

        app.sqslack.send_message(channel, message)

        mock_client.assert_called_once_with(token=token)
        mock_slack.chat_postMessage.assert_called_once_with(channel=channel, text=message, as_user=True)


    @patch('app.sqslack.slack.WebClient')
    def test_lookup_user_by_email(self, mock_client):
        email = 'stephen.rosenthal@seeq.com'
        token = '<not a real Slack API token>'
        os.environ['SLACK_BOT_TOKEN'] = token

        mock_slack = mock_client.return_value
        mock_slack.users_lookupByEmail.return_value.data = {'user': {'id': 'UJ0JNCX19'}}

        result = app.sqslack.lookup_user_by_email(email)

        assert result == '<@UJ0JNCX19>'
        mock_client.assert_called_once_with(token=token)
        mock_slack.users_lookupByEmail.assert_called_once_with(email=email)


    @patch('app.sqslack.slack.WebClient')
    def test_lookup_user_by_email_exception(self, mock_client):
        email = 'stephen.rosenthal@seeq.com'
        token = '<not a real Slack API token>'
        os.environ['SLACK_BOT_TOKEN'] = token

        def raise_error():
            raise RuntimeError('User with email could not be found')

        mock_slack = mock_client.return_value
        mock_slack.users_lookupByEmail.side_effect = lambda *args, **kw: raise_error()

        result = app.sqslack.lookup_user_by_email(email)

        assert result == email
        mock_client.assert_called_once_with(token=token)
        mock_slack.users_lookupByEmail.assert_called_once_with(email=email)


if __name__ == '__main__':
    unittest.main()