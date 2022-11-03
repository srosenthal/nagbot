import unittest
from unittest.mock import patch

import app.common_util as util
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

    def test_can_be_stopped(self):
        running_no_stop_after = self.setup_volume(state='running')
        stopped_no_stop_after = self.setup_volume(state='stopped')

        assert running_no_stop_after.can_be_stopped() is False
        assert stopped_no_stop_after.can_be_stopped() is False

    def test_is_safe_to_stop(self):
        todays_date = util.TODAY_YYYY_MM_DD
        past_date = self.setup_volume(state='available', terminate_after='2019-01-01')
        today_date = self.setup_volume(state='available', terminate_after=todays_date)

        today_warning_str = ' (Nagbot: Warned on ' + todays_date + ')'
        past_date_warned = self.setup_volume(state='available', terminate_after='2019-01-01' + today_warning_str)
        today_date_warned = self.setup_volume(state='available',
                                              terminate_after=todays_date + today_warning_str)
        anything_warned = self.setup_volume(state='available', terminate_after='I Like Pie' + today_warning_str)

        old_warning_str = ' (Nagbot: Warned on ' + util.MIN_TERMINATION_WARNING_YYYY_MM_DD + ')'
        past_date_warned_days_ago = self.setup_volume(state='available', terminate_after='2019-01-01' +
                                                                                         old_warning_str)
        anything_warned_days_ago = self.setup_volume(state='available', terminate_after='I Like Pie' +
                                                                                        old_warning_str)

        wrong_state = self.setup_volume(state='in-use', terminate_after='2019-01-01')
        future_date = self.setup_volume(state='available', terminate_after='2050-01-01')
        unknown_date = self.setup_volume(state='available', terminate_after='TBD')

        assert past_date.is_safe_to_stop(todays_date) is False
        assert today_date.is_safe_to_stop(todays_date) is False
        assert past_date_warned.is_safe_to_stop(todays_date) is False
        assert today_date_warned.is_safe_to_stop(todays_date) is False
        assert anything_warned.is_safe_to_stop(todays_date) is False
        assert past_date_warned_days_ago.is_safe_to_stop(todays_date) is False
        assert anything_warned_days_ago.is_safe_to_stop(todays_date) is False
        assert wrong_state.is_safe_to_stop(todays_date) is False
        assert future_date.is_safe_to_stop(todays_date) is False
        assert unknown_date.is_safe_to_stop(todays_date) is False

    def test_deletable(self):
        todays_date = util.TODAY_YYYY_MM_DD
        past_date = self.setup_volume(state='available', terminate_after='2019-01-01')
        today_date = self.setup_volume(state='available', terminate_after=todays_date)

        today_warning_str = ' (Nagbot: Warned on ' + todays_date + ')'
        past_date_warned = self.setup_volume(state='available', terminate_after='2019-01-01' + today_warning_str)
        today_date_warned = self.setup_volume(state='available',
                                              terminate_after=todays_date + today_warning_str)
        anything_warned = self.setup_volume(state='available', terminate_after='I Like Pie' + today_warning_str)

        old_warning_str = ' (Nagbot: Warned on ' + util.MIN_TERMINATION_WARNING_YYYY_MM_DD + ')'
        past_date_warned_days_ago = self.setup_volume(state='available', terminate_after='2019-01-01' +
                                                                                         old_warning_str)
        anything_warned_days_ago = self.setup_volume(state='available', terminate_after='I Like Pie' +
                                                                                        old_warning_str)

        wrong_state = self.setup_volume(state='in-use', terminate_after='2019-01-01')
        future_date = self.setup_volume(state='available', terminate_after='2050-01-01')
        unknown_date = self.setup_volume(state='available', terminate_after='TBD')

        # These volumes should get a deletion warning
        assert past_date.can_be_terminated(todays_date) is True
        assert today_date.can_be_terminated(todays_date) is True
        assert past_date_warned.can_be_terminated(todays_date) is True
        assert today_date_warned.can_be_terminated(todays_date) is True

        # These volumes should NOT get a deletion warning
        assert wrong_state.can_be_terminated(todays_date) is False
        assert future_date.can_be_terminated(todays_date) is False
        assert unknown_date.can_be_terminated(todays_date) is False
        assert anything_warned.can_be_terminated(todays_date) is False

        # These volumes don't have a warning, so they shouldn't be deleted yet
        assert past_date.is_safe_to_terminate_after_warning(todays_date) is False
        assert today_date.is_safe_to_terminate_after_warning(todays_date) is False
        assert unknown_date.is_safe_to_terminate_after_warning(todays_date) is False
        assert wrong_state.is_safe_to_terminate_after_warning(todays_date) is False
        assert future_date.is_safe_to_terminate_after_warning(todays_date) is False
        assert anything_warned.is_safe_to_terminate_after_warning(todays_date) is False

        # These volumes can be deleted, but not yet
        assert past_date_warned.is_safe_to_terminate_after_warning(todays_date) is False
        assert today_date_warned.is_safe_to_terminate_after_warning(todays_date) is False

        # These volumes have a warning, but are not eligible to add a warning, so we don't delete
        assert anything_warned_days_ago.is_safe_to_terminate_after_warning(todays_date) is False

        # These volumes can be deleted now
        assert past_date_warned_days_ago.is_safe_to_terminate_after_warning(todays_date) is True

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
