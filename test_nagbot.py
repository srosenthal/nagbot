from unittest import TestCase

from nagbot import Nagbot
from sqaws import Instance


class Mock(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# NOTE: These tests are out of date! Don't expect them to pass
class TestNagbot(TestCase):

    def test_notify_empty(self):
        # Return a predefined list of EC2 instances when queried
        sqaws = Mock(list_ec2_instances=lambda: [])

        # Capture any messages sent to Slack
        sent_messages = []
        sqslack = Mock(send_message=lambda channel, message: sent_messages.append((channel, message)))

        nagbot = Nagbot(sqaws, sqslack)
        channel = '#nagbot-testing'
        nagbot.notify(channel)

        # 1: summary, 2: instances to stop
        self.assertEqual(len(sent_messages), 2)
        instances_to_stop_message = sent_messages[1]
        self.assertEqual(instances_to_stop_message[0], channel)
        self.assertEqual(
            instances_to_stop_message[1],
            'No instances are due to be stopped at this time.')

    def test_notify(self):
        # Return a predefined list of EC2 instances when queried
        sqaws = Mock(list_ec2_instances=lambda: [
            Instance(
                name='Due to stop',
                state='running',
                stop_after='2019-01-01',
                terminate_after='Never',
                region_name='us-east-1',
                instance_id='i-12345',
                instance_type='m4.large',
                reason='...',
                operating_system='Linux',
                monthly_price=100.00,
                contact='stephen.rosenthal@seeq.com',
                nagbot_state=''),
            Instance(
                name='Due to terminate',
                state='stopped',
                stop_after='2019-01-01',
                terminate_after='2019-01-01',
                region_name='us-west-1',
                instance_id='i-02468',
                instance_type='m4.xlarge',
                reason='...',
                operating_system='Windows',
                monthly_price=125.00,
                contact='stephen.rosenthal@seeq.com',
                nagbot_state=''),
            Instance(
                name='Keep running',
                state='running',
                stop_after='Never',
                terminate_after='Never',
                region_name='us-west-2',
                instance_id='i-13579',
                instance_type='t2.large',
                reason='...',
                operating_system='Linux',
                monthly_price=150.00,
                contact='stephen.rosenthal@seeq.com',
                nagbot_state=''),
            Instance(
                name='Keep stopped',
                state='stopped',
                stop_after='Never',
                terminate_after='Never',
                region_name='eu-west-1',
                instance_id='i-31415',
                instance_type='c4.xlarge',
                reason='...',
                operating_system='Windows',
                monthly_price=175.00,
                contact='stephen.rosenthal@seeq.com',
                nagbot_state='')
        ], set_tag=lambda region_name, instance_id, tag_name, tag_value: 1)

        # Capture any messages sent to Slack
        sent_messages = []
        sqslack = Mock(
            send_message=lambda channel, message: sent_messages.append(
                (channel, message)))

        nagbot = Nagbot(sqaws, sqslack)
        channel = '#nagbot-testing'
        nagbot.notify(channel)

        # 1: summary, 2: instances to stop
        self.assertEqual(len(sent_messages), 2)
        instances_to_stop_message = sent_messages[1]
        self.assertEqual(instances_to_stop_message[0], channel)
        self.assertRegex(
            instances_to_stop_message[1],
            r'(?m)The following 1 \_running\_ instances are due to be \*STOPPED\*.*')
        # instances_to_terminate_message = sent_messages[2]
        # self.assertEqual(instances_to_terminate_message[0], channel)
        # self.assertRegex(instances_to_terminate_message[1], r'(?m)The following 1 \_stopped\_ instances are due to be \*TERMINATED\*.*')
