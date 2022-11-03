import unittest
from unittest.mock import patch

import app.common_util as util
from app import nagbot
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

        assert running_no_stop_after.is_stoppable_without_warning(is_weekend=False) is True
        assert stopped_no_stop_after.is_stoppable_without_warning(is_weekend=False) is False
        assert past_date.is_stoppable_without_warning(is_weekend=False) is False
        assert notified.is_stoppable_without_warning(is_weekend=False) is True
        # During weekdays do not delete instance with stop after tag "On Weekend"
        assert weekend.is_stoppable_without_warning(is_weekend=False) is False
        # On Weekend delete instance with stop after tag "On Weekend"
        assert weekend.is_stoppable_without_warning(is_weekend=True) is True

    def test_is_stoppable_after_warning(self):
        past_date = self.setup_instance(state='running', stop_after='2019-01-01')
        today_date = self.setup_instance(state='running', stop_after=nagbot.TODAY_YYYY_MM_DD)
        on_weekends = self.setup_instance(state='running', stop_after='On Weekends')

        warning_str = ' (Nagbot: Warned on ' + util.TODAY_YYYY_MM_DD + ')'
        past_date_warned = self.setup_instance(state='running', stop_after='2019-01-01' + warning_str)
        today_date_warned = self.setup_instance(state='running', stop_after=nagbot.TODAY_YYYY_MM_DD + warning_str)
        anything_warned = self.setup_instance(state='running', stop_after='Yummy Udon Noodles' + warning_str)
        on_weekends_warned = self.setup_instance(state='running', stop_after='On Weekends' + warning_str)

        wrong_state = self.setup_instance(state='stopped', stop_after='2019-01-01')
        future_date = self.setup_instance(state='running', stop_after='2050-01-01')
        unknown_date = self.setup_instance(state='running', stop_after='TBD')

        todays_date = util.TODAY_YYYY_MM_DD

        # These instances should get a stop warning
        assert past_date.is_stoppable(todays_date, is_weekend=False) is True
        assert today_date.is_stoppable(todays_date, is_weekend=False) is True
        assert on_weekends.is_stoppable(todays_date, is_weekend=True) is True
        assert unknown_date.is_stoppable(todays_date, is_weekend=False) is True
        assert past_date_warned.is_stoppable(todays_date, is_weekend=False) is True
        assert today_date_warned.is_stoppable(todays_date, is_weekend=False) is True
        assert anything_warned.is_stoppable(todays_date, is_weekend=False) is True
        assert on_weekends_warned.is_stoppable(todays_date, is_weekend=True) is True

        # These instances should NOT g a stop warning
        assert on_weekends.is_stoppable(todays_date, is_weekend=False) is False
        assert on_weekends_warned.is_stoppable(todays_date, is_weekend=False) is False
        assert wrong_state.is_stoppable(todays_date, is_weekend=False) is False
        assert future_date.is_stoppable(todays_date, is_weekend=False) is False

        # These instances don't have a warning, so they shouldn't be stopped yet
        assert past_date.is_safe_to_stop(todays_date, is_weekend=False) is False
        assert today_date.is_safe_to_stop(todays_date, is_weekend=False) is False
        assert wrong_state.is_safe_to_stop(todays_date, is_weekend=False) is False
        assert future_date.is_safe_to_stop(todays_date, is_weekend=False) is False

        # on weekend but with no stop after tag so can be stopped without warning too.
        assert on_weekends.is_safe_to_stop(todays_date, is_weekend=True) is True
        assert unknown_date.is_safe_to_stop(todays_date, is_weekend=False) is True

        # These instances can be stopped right away
        assert past_date_warned.is_safe_to_stop(todays_date, is_weekend=False) is True
        assert today_date_warned.is_safe_to_stop(todays_date, is_weekend=False) is True
        assert on_weekends_warned.is_safe_to_stop(todays_date, is_weekend=True) is True
        assert anything_warned.is_safe_to_stop(todays_date, is_weekend=False) is True

    def test_can_be_terminated(self):
        todays_date = util.TODAY_YYYY_MM_DD
        past_date = self.setup_instance(state='stopped', terminate_after='2019-01-01')
        today_date = self.setup_instance(state='stopped', terminate_after=todays_date)

        today_warning_str = ' (Nagbot: Warned on ' + todays_date + ')'
        past_date_warned = self.setup_instance(state='stopped', terminate_after='2019-01-01' + today_warning_str)
        today_date_warned = self.setup_instance(state='stopped',
                                                terminate_after=todays_date + today_warning_str)
        anything_warned = self.setup_instance(state='stopped', terminate_after='Yummy Udon Noodles' + today_warning_str)

        old_warning_str = ' (Nagbot: Warned on ' + util.MIN_TERMINATION_WARNING_YYYY_MM_DD + ')'
        past_date_warned_days_ago = self.setup_instance(state='stopped', terminate_after='2019-01-01' + old_warning_str)
        anything_warned_days_ago = self.setup_instance(state='stopped',
                                                       terminate_after='Yummy Udon Noodles' + old_warning_str)

        wrong_state = self.setup_instance(state='running', terminate_after='2019-01-01')
        future_date = self.setup_instance(state='stopped', terminate_after='2050-01-01')
        unknown_date = self.setup_instance(state='stopped', terminate_after='TBD')

        # These instances should get a termination warning
        assert past_date.can_be_terminated(todays_date) is True
        assert today_date.can_be_terminated(todays_date) is True
        assert past_date_warned.can_be_terminated(todays_date) is True
        assert today_date_warned.can_be_terminated(todays_date) is True

        # These instances should NOT get a termination warning
        assert wrong_state.can_be_terminated(todays_date) is False
        assert future_date.can_be_terminated(todays_date) is False
        assert unknown_date.can_be_terminated(todays_date) is False
        assert anything_warned.can_be_terminated(todays_date) is False

        # These instances don't have a warning, so they shouldn't be terminated yet
        assert past_date.is_safe_to_terminate_after_warning(todays_date) is False
        assert today_date.is_safe_to_terminate_after_warning(todays_date) is False
        assert unknown_date.is_safe_to_terminate_after_warning(todays_date) is False
        assert wrong_state.is_safe_to_terminate_after_warning(todays_date) is False
        assert future_date.is_safe_to_terminate_after_warning(todays_date) is False
        assert anything_warned.is_safe_to_terminate_after_warning(todays_date) is False

        # These instances can be terminated, but not yet
        assert past_date_warned.is_safe_to_terminate_after_warning(todays_date) is False
        assert today_date_warned.is_safe_to_terminate_after_warning(todays_date) is False

        # These instances have a warning, but are not eligible to add a warning, so we don't terminate
        assert anything_warned_days_ago.is_safe_to_terminate_after_warning(todays_date) is False

        # These instances can be terminated now
        assert past_date_warned_days_ago.is_safe_to_terminate_after_warning(todays_date) is True

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
