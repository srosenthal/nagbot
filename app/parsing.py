import re
from dataclasses import dataclass
from datetime import datetime

import dateutil.parser


# Return a datetime.datetime formatted date, or None if the string is not a date
def parse_date(str: str) -> datetime:
    try:
        return datetime.strptime(str, '%Y-%m-%d')
    except:
        return None


# Take a datetime.datetime and return a string in the appropriate format
def date_to_string(datetime: datetime) -> str:
    if datetime is None:
        return None
    return datetime.strftime('%Y-%m-%d')


@dataclass
class ParsedDate:
    expiry_date: datetime
    on_weekends: bool
    warning_date: datetime

    def __str__(self) -> str:
        result = ''
        if self.on_weekends:
            result = 'On Weekends'
        else:
            result = date_to_string(self.expiry_date)
        if self.warning_date is not None:
            result += ' (Nagbot: Warned on ' + date_to_string(self.warning_date) + ')'
        return result



def parse_date_tag(date_tag: str) -> ParsedDate:
    parsed_date = ParsedDate(None, False, None)

    match = re.match(r'^(\d{4}-\d{2}-\d{2})', date_tag)
    if match:
        expiry_date = datetime.strptime(match.group(1), '%Y-%m-%d')
        parsed_date.expiry_date = expiry_date

    match = re.match(r'^On Weekends', date_tag, re.IGNORECASE)
    if match:
        parsed_date.on_weekends = True

    match = re.match(r'.* \(Nagbot: Warned on (\d{4}-\d{2}-\d{2})\)$', date_tag)
    if match:
        warning_date = datetime.strptime(match.group(1), '%Y-%m-%d')
        parsed_date.warning_date = warning_date

    return parsed_date