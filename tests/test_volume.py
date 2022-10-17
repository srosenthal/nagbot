import unittest
from unittest.mock import patch

from app import resource
from app import nagbot
from app.volume import Volume


class TestVolume(unittest.TestCase):
    @staticmethod
    def setup_volume(state: str, terminate_after: str = '', terminate_after_tag_name: str = ''):
        return Volume(region_name='us-east-1',
                      resource_id='def456',
                      state=state,
                      reason='',
                      resource_type='gp2',
                      ec2_type='volume',
                      name='Quinn',
                      operating_system='Windows',
                      monthly_server_price=0,
                      monthly_storage_price=0,
                      monthly_price=1,
                      stop_after='',
                      terminate_after=terminate_after,
                      contact='quinn',
                      nagbot_state='',
                      eks_nodegroup_name='',
                      stop_after_tag_name='',
                      terminate_after_tag_name=terminate_after_tag_name,
                      nagbot_state_tag_name='',
                      size=1,
                      iops=1,
                      throughput=125)

    def test_stoppable_without_warning(self):
        running_no_stop_after = self.setup_volume(state='running')
        stopped_no_stop_after = self.setup_volume(state='stopped')

        assert Volume.is_stoppable_without_warning(running_no_stop_after) is False
        assert Volume.is_stoppable_without_warning(stopped_no_stop_after) is False

    def test_stoppable(self):
        todays_date = nagbot.TODAY_YYYY_MM_DD
        past_date = self.setup_volume(state='available', terminate_after='2019-01-01')
        today_date = self.setup_volume(state='available', terminate_after=todays_date)

        today_warning_str = ' (Nagbot: Warned on ' + todays_date + ')'
        past_date_warned = self.setup_volume(state='available', terminate_after='2019-01-01' + today_warning_str)
        today_date_warned = self.setup_volume(state='available',
                                              terminate_after=todays_date + today_warning_str)
        anything_warned = self.setup_volume(state='available', terminate_after='I Like Pie' + today_warning_str)

        old_warning_str = ' (Nagbot: Warned on ' + resource.MIN_TERMINATION_WARNING_YYYY_MM_DD + ')'
        past_date_warned_days_ago = self.setup_volume(state='available', terminate_after='2019-01-01' +
                                                                                         old_warning_str)
        anything_warned_days_ago = self.setup_volume(state='available', terminate_after='I Like Pie' +
                                                                                        old_warning_str)

        wrong_state = self.setup_volume(state='in-use', terminate_after='2019-01-01')
        future_date = self.setup_volume(state='available', terminate_after='2050-01-01')
        unknown_date = self.setup_volume(state='available', terminate_after='TBD')

        assert Volume.is_stoppable(past_date, todays_date) is False
        assert Volume.is_stoppable(today_date, todays_date) is False
        assert Volume.is_stoppable(past_date_warned, todays_date) is False
        assert Volume.is_stoppable(today_date_warned, todays_date) is False
        assert Volume.is_stoppable(anything_warned, todays_date) is False
        assert Volume.is_stoppable(past_date_warned_days_ago, todays_date) is False
        assert Volume.is_stoppable(anything_warned_days_ago, todays_date) is False
        assert Volume.is_stoppable(wrong_state, todays_date) is False
        assert Volume.is_stoppable(future_date, todays_date) is False
        assert Volume.is_stoppable(unknown_date, todays_date) is False

    def test_deletable(self):
        todays_date = nagbot.TODAY_YYYY_MM_DD
        past_date = self.setup_volume(state='available', terminate_after='2019-01-01')
        today_date = self.setup_volume(state='available', terminate_after=todays_date)

        today_warning_str = ' (Nagbot: Warned on ' + todays_date + ')'
        past_date_warned = self.setup_volume(state='available', terminate_after='2019-01-01' + today_warning_str)
        today_date_warned = self.setup_volume(state='available',
                                              terminate_after=todays_date + today_warning_str)
        anything_warned = self.setup_volume(state='available', terminate_after='I Like Pie' + today_warning_str)

        old_warning_str = ' (Nagbot: Warned on ' + resource.MIN_TERMINATION_WARNING_YYYY_MM_DD + ')'
        past_date_warned_days_ago = self.setup_volume(state='available', terminate_after='2019-01-01' +
                                                                                         old_warning_str)
        anything_warned_days_ago = self.setup_volume(state='available', terminate_after='I Like Pie' +
                                                                                        old_warning_str)

        wrong_state = self.setup_volume(state='in-use', terminate_after='2019-01-01')
        future_date = self.setup_volume(state='available', terminate_after='2050-01-01')
        unknown_date = self.setup_volume(state='available', terminate_after='TBD')

        # These volumes should get a deletion warning
        assert Volume.is_terminatable(past_date, todays_date) is True
        assert Volume.is_terminatable(today_date, todays_date) is True
        assert Volume.is_terminatable(past_date_warned, todays_date) is True
        assert Volume.is_terminatable(today_date_warned, todays_date) is True

        # These volumes should NOT get a deletion warning
        assert Volume.is_terminatable(wrong_state, todays_date) is False
        assert Volume.is_terminatable(future_date, todays_date) is False
        assert Volume.is_terminatable(unknown_date, todays_date) is False
        assert Volume.is_terminatable(anything_warned, todays_date) is False

        # These volumes don't have a warning, so they shouldn't be deleted yet
        assert Volume.is_safe_to_terminate(past_date, todays_date) is False
        assert Volume.is_safe_to_terminate(today_date, todays_date) is False
        assert Volume.is_safe_to_terminate(unknown_date, todays_date) is False
        assert Volume.is_safe_to_terminate(wrong_state, todays_date) is False
        assert Volume.is_safe_to_terminate(future_date, todays_date) is False
        assert Volume.is_safe_to_terminate(anything_warned, todays_date) is False

        # These volumes can be deleted, but not yet
        assert Volume.is_safe_to_terminate(past_date_warned, todays_date) is False
        assert Volume.is_safe_to_terminate(today_date_warned, todays_date) is False

        # These volumes have a warning, but are not eligible to add a warning, so we don't delete
        assert Volume.is_safe_to_terminate(anything_warned_days_ago, todays_date) is False

        # These volumes can be deleted now
        assert Volume.is_safe_to_terminate(past_date_warned_days_ago, todays_date) is True

    @staticmethod
    @patch('app.volume.boto3.client')
    def test_delete_volume(mock_client):
        mock_volume = TestVolume.setup_volume(state='available')
        mock_ec2 = mock_client.return_value

        assert mock_volume.terminate_resource(dryrun=False)

        mock_client.assert_called_once_with('ec2', region_name=mock_volume.region_name)
        mock_ec2.delete_volume.assert_called_once_with(VolumeId=mock_volume.resource_id)

    @staticmethod
    @patch('app.volume.boto3.client')
    def test_delete_volume_exception(mock_client):
        def raise_error():
            raise RuntimeError('An error occurred (OperationNotPermitted)...')

        mock_volume = TestVolume.setup_volume(state='available')
        mock_ec2 = mock_client.return_value
        mock_ec2.delete_volume.side_effect = lambda *args, **kw: raise_error()

        assert not mock_volume.terminate_resource(dryrun=False)

        mock_client.assert_called_once_with('ec2', region_name=mock_volume.region_name)
        mock_ec2.delete_volume.assert_called_once_with(VolumeId=mock_volume.resource_id)


if __name__ == '__main__':
    unittest.main()
