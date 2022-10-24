import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

from app import resource
from app import nagbot
from app.snapshot import Snapshot


class TestSnapshot(unittest.TestCase):
    @staticmethod
    def setup_snapshot(state: str, terminate_after: str = '', terminate_after_tag_name: str = ''):
        return Snapshot(region_name='us-east-1',
                        resource_id='def456',
                        state=state,
                        reason='',
                        resource_type='standard',
                        ec2_type='snapshot',
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
                        size=1,
                        iops=1,
                        throughput=125)

    def test_stoppable_without_warning(self):
        completed_no_stop_after = self.setup_snapshot(state='completed')
        pending_no_stop_after = self.setup_snapshot(state='pending')

        assert Snapshot.is_stoppable_without_warning(completed_no_stop_after) is False
        assert Snapshot.is_stoppable_without_warning(pending_no_stop_after) is False

    def test_stoppable(self):
        todays_date = nagbot.TODAY_YYYY_MM_DD
        past_date = self.setup_snapshot(state='completed', terminate_after='2019-01-01')
        today_date = self.setup_snapshot(state='completed', terminate_after=todays_date)

        today_warning_str = ' (Nagbot: Warned on ' + todays_date + ')'
        past_date_warned = self.setup_snapshot(state='completed', terminate_after='2019-01-01' + today_warning_str)
        today_date_warned = self.setup_snapshot(state='completed',
                                                terminate_after=todays_date + today_warning_str)
        anything_warned = self.setup_snapshot(state='completed', terminate_after='I Like Pie' + today_warning_str)

        old_warning_str = ' (Nagbot: Warned on ' + resource.MIN_TERMINATION_WARNING_YYYY_MM_DD + ')'
        past_date_warned_days_ago = self.setup_snapshot(state='completed', terminate_after='2019-01-01' +
                                                                                           old_warning_str)
        anything_warned_days_ago = self.setup_snapshot(state='completed', terminate_after='I Like Pie' +
                                                                                          old_warning_str)

        wrong_state = self.setup_snapshot(state='pending', terminate_after='2019-01-01')
        future_date = self.setup_snapshot(state='completed', terminate_after='2050-01-01')
        unknown_date = self.setup_snapshot(state='completed', terminate_after='TBD')

        assert Snapshot.is_stoppable(past_date, todays_date) is False
        assert Snapshot.is_stoppable(today_date, todays_date) is False
        assert Snapshot.is_stoppable(past_date_warned, todays_date) is False
        assert Snapshot.is_stoppable(today_date_warned, todays_date) is False
        assert Snapshot.is_stoppable(anything_warned, todays_date) is False
        assert Snapshot.is_stoppable(past_date_warned_days_ago, todays_date) is False
        assert Snapshot.is_stoppable(anything_warned_days_ago, todays_date) is False
        assert Snapshot.is_stoppable(wrong_state, todays_date) is False
        assert Snapshot.is_stoppable(future_date, todays_date) is False
        assert Snapshot.is_stoppable(unknown_date, todays_date) is False

    def test_deletable(self):
        todays_date = nagbot.TODAY_YYYY_MM_DD
        past_date = self.setup_snapshot(state='completed', terminate_after='2019-01-01')
        today_date = self.setup_snapshot(state='completed', terminate_after=todays_date)

        today_warning_str = ' (Nagbot: Warned on ' + todays_date + ')'
        past_date_warned = self.setup_snapshot(state='completed', terminate_after='2019-01-01' + today_warning_str)
        today_date_warned = self.setup_snapshot(state='completed',
                                                terminate_after=todays_date + today_warning_str)
        anything_warned = self.setup_snapshot(state='completed', terminate_after='I Like Pie' + today_warning_str)

        old_warning_str = ' (Nagbot: Warned on ' + resource.MIN_TERMINATION_WARNING_YYYY_MM_DD + ')'
        past_date_warned_days_ago = self.setup_snapshot(state='completed', terminate_after='2019-01-01' +
                                                                                           old_warning_str)
        anything_warned_days_ago = self.setup_snapshot(state='completed', terminate_after='I Like Pie' +
                                                                                          old_warning_str)

        wrong_state = self.setup_snapshot(state='pending', terminate_after='2019-01-01')
        future_date = self.setup_snapshot(state='completed', terminate_after='2050-01-01')
        unknown_date = self.setup_snapshot(state='completed', terminate_after='TBD')

        # These snapshots should get a deletion warning
        assert Snapshot.is_terminatable(past_date, todays_date) is True
        assert Snapshot.is_terminatable(today_date, todays_date) is True
        assert Snapshot.is_terminatable(past_date_warned, todays_date) is True
        assert Snapshot.is_terminatable(today_date_warned, todays_date) is True

        # These snapshots should NOT get a deletion warning
        assert Snapshot.is_terminatable(wrong_state, todays_date) is False
        assert Snapshot.is_terminatable(future_date, todays_date) is False
        assert Snapshot.is_terminatable(unknown_date, todays_date) is False
        assert Snapshot.is_terminatable(anything_warned, todays_date) is False

        # These snapshots don't have a warning, so they shouldn't be deleted yet
        assert Snapshot.is_safe_to_terminate(past_date, todays_date) is False
        assert Snapshot.is_safe_to_terminate(today_date, todays_date) is False
        assert Snapshot.is_safe_to_terminate(unknown_date, todays_date) is False
        assert Snapshot.is_safe_to_terminate(wrong_state, todays_date) is False
        assert Snapshot.is_safe_to_terminate(future_date, todays_date) is False
        assert Snapshot.is_safe_to_terminate(anything_warned, todays_date) is False

        # These snapshots can be deleted, but not yet
        assert Snapshot.is_safe_to_terminate(past_date_warned, todays_date) is False
        assert Snapshot.is_safe_to_terminate(today_date_warned, todays_date) is False

        # These snapshots have a warning, but are not eligible to add a warning, so we don't delete
        assert Snapshot.is_safe_to_terminate(anything_warned_days_ago, todays_date) is False

        # These snapshots can be deleted now
        assert Snapshot.is_safe_to_terminate(past_date_warned_days_ago, todays_date) is True

    @staticmethod
    @patch('app.snapshot.boto3.client')
    def test_delete_snapshot(mock_client):
        mock_snapshot = TestSnapshot.setup_snapshot(state='completed')

        mock_ec2 = mock_client.return_value
        # _aws is included in variable name to differentiate between Snapshot class of NagBot and Snapshot class of AWS
        mock_snapshot_aws = MagicMock()
        mock_ec2.Snapshot.return_value = mock_snapshot_aws

        assert mock_snapshot.terminate_resource(dryrun=False)

        mock_client.assert_called_once_with('ec2', region_name=mock_snapshot.region_name)
        mock_snapshot_aws.delete.assert_called_once()

    @staticmethod
    @patch('app.snapshot.boto3.client')
    def test_delete_snapshot_exception(mock_client):
        def raise_error():
            raise RuntimeError('An error occurred (OperationNotPermitted)...')

        mock_snapshot = TestSnapshot.setup_snapshot(state='completed')

        mock_ec2 = mock_client.return_value
        mock_snapshot_aws = MagicMock()
        mock_ec2.Snapshot.return_value = mock_snapshot_aws
        mock_snapshot_aws.delete.side_effect = lambda *args, **kw: raise_error()

        assert not mock_snapshot.terminate_resource(dryrun=False)

        mock_client.assert_called_once_with('ec2', region_name=mock_snapshot.region_name)
        mock_snapshot_aws.delete.assert_called_once()


if __name__ == '__main__':
    unittest.main()
