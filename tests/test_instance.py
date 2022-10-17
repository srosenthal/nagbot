import unittest
from unittest.mock import patch

from app import nagbot
from app import resource
from app.instance import Instance


class TestInstance(unittest.TestCase):
    @staticmethod
    def setup_instance(state: str, stop_after: str = '', terminate_after: str = '',
                       stop_after_tag_name: str = '', terminate_after_tag_name: str = ''):
        return Instance(region_name='us-east-1',
                        resource_id='abc123',
                        state=state,
                        reason='',
                        resource_type='m4.xlarge',
                        ec2_type='instance',
                        name='Stephen',
                        operating_system='linux',
                        monthly_price=1,
                        monthly_server_price=2,
                        monthly_storage_price=3,
                        stop_after=stop_after,
                        terminate_after=terminate_after,
                        contact='stephen',
                        nagbot_state='',
                        eks_nodegroup_name='',
                        stop_after_tag_name=stop_after_tag_name,
                        terminate_after_tag_name=terminate_after_tag_name,
                        nagbot_state_tag_name='NagbotState',
                        size=0,
                        iops=0,
                        throughput=0)

    def test_stoppable_without_warning(self):
        running_no_stop_after = self.setup_instance(state='running')
        stopped_no_stop_after = self.setup_instance(state='stopped')
        past_date = self.setup_instance(state='running', stop_after='2019-01-01')
        notified = self.setup_instance(state='running', stop_after='(Nagbot: Warned on 2022-10-14)')
        weekend = self.setup_instance(state='running', stop_after='On Weekends')

        assert Instance.is_stoppable_without_warning(running_no_stop_after) is True
        assert Instance.is_stoppable_without_warning(stopped_no_stop_after) is False
        assert Instance.is_stoppable_without_warning(past_date) is False
        assert Instance.is_stoppable_without_warning(notified) is True
        # During weekdays do not delete instance with stop after tag "On Weekend"
        assert Instance.is_stoppable_without_warning(weekend, is_weekend=False) is False
        # On Weekend delete instance with stop after tag "On Weekend"
        assert Instance.is_stoppable_without_warning(weekend, is_weekend=True) is True

    def test_stoppable(self):
        past_date = self.setup_instance(state='running', stop_after='2019-01-01')
        today_date = self.setup_instance(state='running', stop_after=nagbot.TODAY_YYYY_MM_DD)
        on_weekends = self.setup_instance(state='running', stop_after='On Weekends')

        warning_str = ' (Nagbot: Warned on ' + nagbot.TODAY_YYYY_MM_DD + ')'
        past_date_warned = self.setup_instance(state='running', stop_after='2019-01-01' + warning_str)
        today_date_warned = self.setup_instance(state='running', stop_after=nagbot.TODAY_YYYY_MM_DD + warning_str)
        anything_warned = self.setup_instance(state='running', stop_after='Yummy Udon Noodles' + warning_str)
        on_weekends_warned = self.setup_instance(state='running', stop_after='On Weekends' + warning_str)

        wrong_state = self.setup_instance(state='stopped', stop_after='2019-01-01')
        future_date = self.setup_instance(state='running', stop_after='2050-01-01')
        unknown_date = self.setup_instance(state='running', stop_after='TBD')

        todays_date = nagbot.TODAY_YYYY_MM_DD

        # These instances should get a stop warning
        assert Instance.is_stoppable(past_date, todays_date) is True
        assert Instance.is_stoppable(today_date, todays_date) is True
        assert Instance.is_stoppable(on_weekends, todays_date, is_weekend=True) is True
        assert Instance.is_stoppable(unknown_date, todays_date) is True
        assert Instance.is_stoppable(past_date_warned, todays_date) is True
        assert Instance.is_stoppable(today_date_warned, todays_date) is True
        assert Instance.is_stoppable(anything_warned, todays_date) is True
        assert Instance.is_stoppable(on_weekends_warned, todays_date, is_weekend=True) is True

        # These instances should NOT get a stop warning
        assert Instance.is_stoppable(on_weekends, todays_date, is_weekend=False) is False
        assert Instance.is_stoppable(on_weekends_warned, todays_date, is_weekend=False) is False
        assert Instance.is_stoppable(wrong_state, todays_date) is False
        assert Instance.is_stoppable(future_date, todays_date) is False

        # These instances don't have a warning, so they shouldn't be stopped yet
        assert Instance.is_safe_to_stop(past_date, todays_date) is False
        assert Instance.is_safe_to_stop(today_date, todays_date) is False
        assert Instance.is_safe_to_stop(on_weekends, todays_date, is_weekend=True) is False
        assert Instance.is_safe_to_stop(unknown_date, todays_date) is False
        assert Instance.is_safe_to_stop(wrong_state, todays_date) is False
        assert Instance.is_safe_to_stop(future_date, todays_date) is False

        # These instances can be stopped right away
        assert Instance.is_safe_to_stop(past_date_warned, todays_date) is True
        assert Instance.is_safe_to_stop(today_date_warned, todays_date) is True
        assert Instance.is_safe_to_stop(on_weekends_warned, todays_date, is_weekend=True) is True
        assert Instance.is_safe_to_stop(anything_warned, todays_date) is True

    def test_terminatable(self):
        todays_date = nagbot.TODAY_YYYY_MM_DD
        past_date = self.setup_instance(state='stopped', terminate_after='2019-01-01')
        today_date = self.setup_instance(state='stopped', terminate_after=todays_date)

        today_warning_str = ' (Nagbot: Warned on ' + todays_date + ')'
        past_date_warned = self.setup_instance(state='stopped', terminate_after='2019-01-01' + today_warning_str)
        today_date_warned = self.setup_instance(state='stopped',
                                                terminate_after=todays_date + today_warning_str)
        anything_warned = self.setup_instance(state='stopped', terminate_after='Yummy Udon Noodles' + today_warning_str)

        old_warning_str = ' (Nagbot: Warned on ' + resource.MIN_TERMINATION_WARNING_YYYY_MM_DD + ')'
        past_date_warned_days_ago = self.setup_instance(state='stopped', terminate_after='2019-01-01' + old_warning_str)
        anything_warned_days_ago = self.setup_instance(state='stopped',
                                                       terminate_after='Yummy Udon Noodles' + old_warning_str)

        wrong_state = self.setup_instance(state='running', terminate_after='2019-01-01')
        future_date = self.setup_instance(state='stopped', terminate_after='2050-01-01')
        unknown_date = self.setup_instance(state='stopped', terminate_after='TBD')

        # These instances should get a termination warning
        assert Instance.is_terminatable(past_date, todays_date) is True
        assert Instance.is_terminatable(today_date, todays_date) is True
        assert Instance.is_terminatable(past_date_warned, todays_date) is True
        assert Instance.is_terminatable(today_date_warned, todays_date) is True

        # These instances should NOT get a termination warning
        assert Instance.is_terminatable(wrong_state, todays_date) is False
        assert Instance.is_terminatable(future_date, todays_date) is False
        assert Instance.is_terminatable(unknown_date, todays_date) is False
        assert Instance.is_terminatable(anything_warned, todays_date) is False

        # These instances don't have a warning, so they shouldn't be terminated yet
        assert Instance.is_safe_to_terminate(past_date, todays_date) is False
        assert Instance.is_safe_to_terminate(today_date, todays_date) is False
        assert Instance.is_safe_to_terminate(unknown_date, todays_date) is False
        assert Instance.is_safe_to_terminate(wrong_state, todays_date) is False
        assert Instance.is_safe_to_terminate(future_date, todays_date) is False
        assert Instance.is_safe_to_terminate(anything_warned, todays_date) is False

        # These instances can be terminated, but not yet
        assert Instance.is_safe_to_terminate(past_date_warned, todays_date) is False
        assert Instance.is_safe_to_terminate(today_date_warned, todays_date) is False

        # These instances have a warning, but are not eligible to add a warning, so we don't terminate
        assert Instance.is_safe_to_terminate(anything_warned_days_ago, todays_date) is False

        # These instances can be terminated now
        assert Instance.is_safe_to_terminate(past_date_warned_days_ago, todays_date) is True

    def test_instance_stop_terminate_str(self):
        lowercase_instance = self.setup_instance(state='running', stop_after_tag_name='stopafter',
                                                 terminate_after_tag_name='terminateafter')
        uppercase_instance = self.setup_instance(state='running', stop_after_tag_name='STOPAFTER',
                                                 terminate_after_tag_name='TERMINATEAFTER')
        mixed_case_instance = self.setup_instance(state='running', stop_after_tag_name='StopAfter',
                                                  terminate_after_tag_name='TerminateAfter')

        # Ensure stop_after_str and terminate_after_str fields are correct in each instance
        assert lowercase_instance.stop_after_tag_name == 'stopafter'
        assert lowercase_instance.terminate_after_tag_name == 'terminateafter'
        assert uppercase_instance.stop_after_tag_name == 'STOPAFTER'
        assert uppercase_instance.terminate_after_tag_name == 'TERMINATEAFTER'
        assert mixed_case_instance.stop_after_tag_name == 'StopAfter'
        assert mixed_case_instance.terminate_after_tag_name == 'TerminateAfter'

    @staticmethod
    @patch('app.instance.boto3.client')
    def test_terminate_instance(mock_client):
        mock_instance = TestInstance.setup_instance(state='stopped')
        mock_ec2 = mock_client.return_value

        assert mock_instance.terminate_resource(dryrun=False)

        mock_client.assert_called_once_with('ec2', region_name=mock_instance.region_name)
        mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=[mock_instance.resource_id])

    @staticmethod
    @patch('app.instance.boto3.client')
    def test_terminate_instance_exception(mock_client):
        # Note: I've seen the call to terminate_instance fail when termination protection is enabled
        def raise_error():
            # The real Boto SDK raises botocore.exceptions.ClientError, but this is close enough
            raise RuntimeError('An error occurred (OperationNotPermitted)...')

        mock_instance = TestInstance.setup_instance(state='stopped')
        mock_ec2 = mock_client.return_value
        mock_ec2.terminate_instances.side_effect = lambda *args, **kw: raise_error()

        assert not mock_instance.terminate_resource(dryrun=False)

        mock_client.assert_called_once_with('ec2', region_name=mock_instance.region_name)
        mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=[mock_instance.resource_id])


if __name__ == '__main__':
    unittest.main()
