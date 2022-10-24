import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

from app import resource
from app import nagbot
from app.ami import Ami


class TestAmi(unittest.TestCase):
    @staticmethod
    def setup_ami(state: str, terminate_after: str = '', terminate_after_tag_name: str = ''):
        return Ami(region_name='us-east-1',
                   resource_id='def456',
                   state=state,
                   reason='',
                   resource_type='machine',
                   ec2_type='ami',
                   name='Ali',
                   operating_system='Windows',
                   monthly_price=1,
                   stop_after='',
                   terminate_after=terminate_after,
                   contact='Ali',
                   nagbot_state='',
                   eks_nodegroup_name='',
                   stop_after_tag_name='',
                   terminate_after_tag_name=terminate_after_tag_name,
                   nagbot_state_tag_name='',
                   iops=1,
                   throughput=125
                   )

    def test_stoppable_without_warning(self):
        available_no_stop_after = self.setup_ami(state='available')
        pending_no_stop_after = self.setup_ami(state='pending')

        assert Ami.is_stoppable_without_warning(available_no_stop_after) is False
        assert Ami.is_stoppable_without_warning(pending_no_stop_after) is False

    def test_stoppable(self):
        todays_date = nagbot.TODAY_YYYY_MM_DD
        past_date = self.setup_ami(state='available', terminate_after='2019-01-01')
        today_date = self.setup_ami(state='available', terminate_after=todays_date)

        today_warning_str = ' (Nagbot: Warned on ' + todays_date + ')'
        past_date_warned = self.setup_ami(state='available', terminate_after='2019-01-01' + today_warning_str)
        today_date_warned = self.setup_ami(state='available',
                                           terminate_after=todays_date + today_warning_str)
        anything_warned = self.setup_ami(state='available', terminate_after='I Like lasagna' + today_warning_str)

        old_warning_str = ' (Nagbot: Warned on ' + resource.MIN_TERMINATION_WARNING_YYYY_MM_DD + ')'
        past_date_warned_days_ago = self.setup_ami(state='available', terminate_after='2019-01-01' +
                                                   old_warning_str)
        anything_warned_days_ago = self.setup_ami(state='available', terminate_after='I Like lasagna' +
                                                  old_warning_str)

        wrong_state = self.setup_ami(state='pending', terminate_after='2019-01-01')
        future_date = self.setup_ami(state='available', terminate_after='2050-01-01')
        unknown_date = self.setup_ami(state='available', terminate_after='TBD')

        assert Ami.is_stoppable(past_date, todays_date) is False
        assert Ami.is_stoppable(today_date, todays_date) is False
        assert Ami.is_stoppable(past_date_warned, todays_date) is False
        assert Ami.is_stoppable(today_date_warned, todays_date) is False
        assert Ami.is_stoppable(anything_warned, todays_date) is False
        assert Ami.is_stoppable(past_date_warned_days_ago, todays_date) is False
        assert Ami.is_stoppable(anything_warned_days_ago, todays_date) is False
        assert Ami.is_stoppable(wrong_state, todays_date) is False
        assert Ami.is_stoppable(future_date, todays_date) is False
        assert Ami.is_stoppable(unknown_date, todays_date) is False

    def test_deletable(self):
        todays_date = nagbot.TODAY_YYYY_MM_DD
        past_date = self.setup_ami(state='available', terminate_after='2019-01-01')
        today_date = self.setup_ami(state='available', terminate_after=todays_date)

        today_warning_str = ' (Nagbot: Warned on ' + todays_date + ')'
        past_date_warned = self.setup_ami(state='available', terminate_after='2019-01-01' + today_warning_str)
        today_date_warned = self.setup_ami(state='available',
                                              terminate_after=todays_date + today_warning_str)
        anything_warned = self.setup_ami(state='available', terminate_after='I Like Lasagna' + today_warning_str)

        old_warning_str = ' (Nagbot: Warned on ' + resource.MIN_TERMINATION_WARNING_YYYY_MM_DD + ')'
        past_date_warned_days_ago = self.setup_ami(state='available', terminate_after='2019-01-01' +
                                                                                         old_warning_str)
        anything_warned_days_ago = self.setup_ami(state='available', terminate_after='I Like Pie' +
                                                                                        old_warning_str)

        wrong_state = self.setup_ami(state='pending', terminate_after='2019-01-01')
        future_date = self.setup_ami(state='available', terminate_after='2050-01-01')
        unknown_date = self.setup_ami(state='available', terminate_after='TBD')

        # These amis should get a deletion warning
        assert Ami.is_terminatable(past_date, todays_date) is True
        assert Ami.is_terminatable(today_date, todays_date) is True
        assert Ami.is_terminatable(past_date_warned, todays_date) is True
        assert Ami.is_terminatable(today_date_warned, todays_date) is True

        # These amis should NOT get a deletion warning
        assert Ami.is_terminatable(wrong_state, todays_date) is False
        assert Ami.is_terminatable(future_date, todays_date) is False
        assert Ami.is_terminatable(unknown_date, todays_date) is False
        assert Ami.is_terminatable(anything_warned, todays_date) is False

        # These amis don't have a warning, so they shouldn't be deleted yet
        assert Ami.is_safe_to_terminate(past_date, todays_date) is False
        assert Ami.is_safe_to_terminate(today_date, todays_date) is False
        assert Ami.is_safe_to_terminate(unknown_date, todays_date) is False
        assert Ami.is_safe_to_terminate(wrong_state, todays_date) is False
        assert Ami.is_safe_to_terminate(future_date, todays_date) is False
        assert Ami.is_safe_to_terminate(anything_warned, todays_date) is False

        # These amis can be deleted, but not yet
        assert Ami.is_safe_to_terminate(past_date_warned, todays_date) is False
        assert Ami.is_safe_to_terminate(today_date_warned, todays_date) is False

        # These amis have a warning, but are not eligible to add a warning, so we don't delete
        assert Ami.is_safe_to_terminate(anything_warned_days_ago, todays_date) is False

        # These amis can be deleted now
        assert Ami.is_safe_to_terminate(past_date_warned_days_ago, todays_date) is True

    @staticmethod
    @patch('app.ami.boto3.resource')
    def test_delete_snapshot(mock_resource):
        mock_ami = TestAmi.setup_ami(state='available')

        mock_ec2 = mock_resource.return_value
        mock_image = MagicMock()
        mock_ec2.Image.return_value = mock_image

        assert mock_ami.terminate_resource(dryrun=False)

        mock_resource.assert_called_once_with('ec2', region_name=mock_ami.region_name)
        mock_image.deregister.assert_called_once()

    @staticmethod
    @patch('app.snapshot.boto3.resource')
    def test_delete_snapshot_exception(mock_resource):
        def raise_error():
            raise RuntimeError('An error occurred (OperationNotPermitted)...')

        mock_ami = TestAmi.setup_ami(state='available')
        mock_ec2 = mock_resource.return_value
        mock_image = MagicMock()
        mock_ec2.Image.return_value = mock_image
        mock_image.deregister.side_effect = lambda *args, **kw: raise_error()

        assert not mock_ami.terminate_resource(dryrun=False)

        mock_resource.assert_called_once_with('ec2', region_name=mock_ami.region_name)
        mock_image.deregister.assert_called_once()


if __name__ == '__main__':
    unittest.main()
