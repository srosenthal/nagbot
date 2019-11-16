from datetime import datetime

import parsing;

import unittest

class TestParsing(unittest.TestCase):
    def test_parse_date(self):
        def is_date(str):
            return parsing.parse_date(str) is not None

        # ISO-8601 is preferred
        assert is_date('2019-01-01')
        assert is_date('2019-12-31')

        # This format apparently works too
        assert is_date('2019-1-2')

        # Other formats are meaningful, but not supported by the parser
        assert not is_date('2019/01/02')
        assert not is_date('01/02/2019')
        assert not is_date('January 2, 2019')
        assert not is_date('Jan. 2, 2019')

        assert not is_date('9999-99-99')
        assert not is_date('2019-02-31')
        assert not is_date('2019-11-31')
        assert not is_date('abc')
        assert not is_date('')
        assert not is_date(None)
        assert not is_date(123)


    def test_date_to_string(self):
        def roundtrip(str):
            datetime = parsing.parse_date(str)
            return parsing.date_to_string(datetime)

        assert roundtrip('2019-01-01') == '2019-01-01'
        assert roundtrip('2019-12-31') == '2019-12-31'

        assert roundtrip('2019-1-2') == '2019-01-02'


    def test_parse_date_tag(self):
        parsed = parsing.parse_date_tag('2019-01-01')
        assert parsed.expiry_date == datetime(2019, 1, 1)
        assert parsed.on_weekends == False
        assert parsed.warning_date == None

        parsed = parsing.parse_date_tag('2019-01-01 (Nagbot: Warned on 2019-02-01)')
        assert parsed.expiry_date == datetime(2019, 1, 1)
        assert parsed.on_weekends == False
        assert parsed.warning_date == datetime(2019, 2, 1)

        parsed = parsing.parse_date_tag('On Weekends')
        assert parsed.expiry_date == None
        assert parsed.on_weekends == True
        assert parsed.warning_date == None

        parsed = parsing.parse_date_tag('oN wEeKeNdS')
        assert parsed.expiry_date == None
        assert parsed.on_weekends == True
        assert parsed.warning_date == None

        parsed = parsing.parse_date_tag('On Weekends (Nagbot: Warned on 2019-02-01)')
        assert parsed.expiry_date == None
        assert parsed.on_weekends == True
        assert parsed.warning_date == datetime(2019, 2, 1)


    def test_print_date_tag(self):
        def roundtrip(date_tag):
            parsed_date_tag = parsing.parse_date_tag(date_tag)
            return str(parsed_date_tag)

        assert roundtrip('2019-01-01') == '2019-01-01'
        assert roundtrip('2019-01-01 (Nagbot: Warned on 2019-02-01)') \
               == '2019-01-01 (Nagbot: Warned on 2019-02-01)'

        assert roundtrip('On Weekends') == 'On Weekends'
        assert roundtrip('oN wEeKeNdS') == 'On Weekends'
        assert roundtrip('On Weekends (Nagbot: Warned on 2019-02-01)') \
               == 'On Weekends (Nagbot: Warned on 2019-02-01)'

if __name__ == '__main__':
    unittest.main()