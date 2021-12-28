import unittest

from app import nagbot
from app.sqaws import Instance


class TestNagbot(unittest.TestCase):
    @staticmethod
    def setup_instance(state: str, stop_after: str = '', terminate_after: str = ''):
        return Instance(region_name='us-east-1',
                        instance_id='abc123',
                        state=state,
                        reason='',
                        instance_type='m4.xlarge',
                        name='Stephen',
                        operating_system='linux',
                        monthly_price=1,
                        monthly_server_price=2,
                        monthly_storage_price=3,
                        stop_after=stop_after,
                        terminate_after=terminate_after,
                        contact='stephen',
                        nagbot_state='',
                        eks_nodegroup_name='')

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

        # These instances should get a stop warning
        assert nagbot.is_stoppable(past_date) is True
        assert nagbot.is_stoppable(today_date) is True
        assert nagbot.is_stoppable(on_weekends, is_weekend=True) is True
        assert nagbot.is_stoppable(unknown_date) is True
        assert nagbot.is_stoppable(past_date_warned) is True
        assert nagbot.is_stoppable(today_date_warned) is True
        assert nagbot.is_stoppable(anything_warned) is True
        assert nagbot.is_stoppable(on_weekends_warned, is_weekend=True) is True

        # These instances should NOT get a stop warning
        assert nagbot.is_stoppable(on_weekends, is_weekend=False) is False
        assert nagbot.is_stoppable(on_weekends_warned, is_weekend=False) is False
        assert nagbot.is_stoppable(wrong_state) is False
        assert nagbot.is_stoppable(future_date) is False

        # These instances don't have a warning, so they shouldn't be stopped yet
        assert nagbot.is_safe_to_stop(past_date) is False
        assert nagbot.is_safe_to_stop(today_date) is False
        assert nagbot.is_safe_to_stop(on_weekends, is_weekend=True) is False
        assert nagbot.is_safe_to_stop(unknown_date) is False
        assert nagbot.is_safe_to_stop(wrong_state) is False
        assert nagbot.is_safe_to_stop(future_date) is False

        # These instances can be stopped right away
        assert nagbot.is_safe_to_stop(past_date_warned) is True
        assert nagbot.is_safe_to_stop(today_date_warned) is True
        assert nagbot.is_safe_to_stop(on_weekends_warned, is_weekend=True) is True
        assert nagbot.is_safe_to_stop(anything_warned) is True

    def test_terminatable(self):
        past_date = self.setup_instance(state='stopped', terminate_after='2019-01-01')
        today_date = self.setup_instance(state='stopped', terminate_after=nagbot.TODAY_YYYY_MM_DD)

        today_warning_str = ' (Nagbot: Warned on ' + nagbot.TODAY_YYYY_MM_DD + ')'
        past_date_warned = self.setup_instance(state='stopped', terminate_after='2019-01-01' + today_warning_str)
        today_date_warned = self.setup_instance(state='stopped',
                                                terminate_after=nagbot.TODAY_YYYY_MM_DD + today_warning_str)
        anything_warned = self.setup_instance(state='stopped', terminate_after='Yummy Udon Noodles' + today_warning_str)

        old_warning_str = ' (Nagbot: Warned on ' + nagbot.MIN_TERMINATION_WARNING_YYYY_MM_DD + ')'
        past_date_warned_days_ago = self.setup_instance(state='stopped', terminate_after='2019-01-01' + old_warning_str)
        anything_warned_days_ago = self.setup_instance(state='stopped',
                                                       terminate_after='Yummy Udon Noodles' + old_warning_str)

        wrong_state = self.setup_instance(state='running', terminate_after='2019-01-01')
        future_date = self.setup_instance(state='stopped', terminate_after='2050-01-01')
        unknown_date = self.setup_instance(state='stopped', terminate_after='TBD')

        # These instances should get a termination warning
        assert nagbot.is_terminatable(past_date) is True
        assert nagbot.is_terminatable(today_date) is True
        assert nagbot.is_terminatable(past_date_warned) is True
        assert nagbot.is_terminatable(today_date_warned) is True

        # These instances should NOT get a termination warning
        assert nagbot.is_terminatable(wrong_state) is False
        assert nagbot.is_terminatable(future_date) is False
        assert nagbot.is_terminatable(unknown_date) is False
        assert nagbot.is_terminatable(anything_warned) is False

        # These instances don't have a warning, so they shouldn't be terminated yet
        assert nagbot.is_safe_to_terminate(past_date) is False
        assert nagbot.is_safe_to_terminate(today_date) is False
        assert nagbot.is_safe_to_terminate(unknown_date) is False
        assert nagbot.is_safe_to_terminate(wrong_state) is False
        assert nagbot.is_safe_to_terminate(future_date) is False
        assert nagbot.is_safe_to_terminate(anything_warned) is False

        # These instances can be terminated, but not yet
        assert nagbot.is_safe_to_terminate(past_date_warned) is False
        assert nagbot.is_safe_to_terminate(today_date_warned) is False

        # These instances have a warning, but are not eligible to add a warning, so we don't terminate
        assert nagbot.is_safe_to_terminate(anything_warned_days_ago) is False

        # These instances can be terminated now
        assert nagbot.is_safe_to_terminate(past_date_warned_days_ago) is True


if __name__ == '__main__':
    unittest.main()
