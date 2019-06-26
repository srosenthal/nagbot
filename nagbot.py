__author__ = "Stephen Rosenthal"
__version__ = "1.3.0"
__license__ = "MIT"

import argparse
import re
import sys
import traceback
from datetime import datetime, timedelta

import gdocs
import sqaws
import sqslack

TODAY_YYYY_MM_DD = datetime.today().strftime('%Y-%m-%d')
YESTERDAY_YYYY_MM_DD = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')


"""
PREREQUISITES:
1. An AWS account with credentials set up in a standard place (environment variables, home directory, etc.)
2. The AWS credentials must have access to the EC2 APIs "describe_regions" and "describe_instances"
3. PIP dependencies "awspricing", "boto3", "slackclient".
4. Environment variable "SLACK_BOT_TOKEN" containing a token allowing messages to be posted to Slack.
"""


class Nagbot(object):

    def __init__(self, aws, slack):
        self.aws = aws
        self.slack = slack

    def notify(self, channel):
        instances = self.aws.list_ec2_instances()

        num_running_instances = sum(1 for i in instances if i.state == 'running')
        num_total_instances = sum(1 for i in instances)
        running_monthly_cost = money_to_string(sum(i.monthly_price for i in instances))

        summary_msg = "Hi, I'm Nagbot v{} :wink: My job is to make sure we don't forget about unwanted AWS servers and waste money!\n".format(__version__)
        summary_msg = summary_msg + "Here is some data...\n"
        summary_msg = summary_msg + "We have {} running EC2 instances right now and {} total.\n".format(num_running_instances,
                                                                                                num_total_instances)
        summary_msg = summary_msg + "If we continue to run these instances all month, it would cost {}.\n" \
            .format(running_monthly_cost)
        self.slack.send_message(channel, summary_msg)

        # From here on, exclude "whitelisted" instances
        all_instances = instances
        instances = sorted((i for i in instances if not is_whitelisted(i)), key=lambda i: i.name)

        instances_to_stop = get_stoppable_instances(instances)
        if len(instances_to_stop) > 0:
            detail_msg = 'The following %d _running_ instances are due to be *STOPPED*, based on the "Stop after" tag:\n' % len(instances_to_stop)
            for i in instances_to_stop:
                contact = self.slack.lookup_user_by_email(i.contact)
                detail_msg = detail_msg + make_instance_summary(i) + ', StopAfter={}, MonthlyPrice={}, Contact={}\n' \
                    .format(i.stop_after, money_to_string(i.monthly_price), contact)
                self.aws.set_tag(i.region_name, i.instance_id, 'Nagbot State', 'Stop warning ' + TODAY_YYYY_MM_DD)
        else:
            detail_msg = 'No instances are due to be stopped at this time.\n'

        # Collect all of the data to a Google Sheet
        try:
            header = all_instances[0].to_header()
            body = [i.to_list() for i in all_instances]
            spreadsheet_url = gdocs.write_to_spreadsheet([header] + body)
            detail_msg = detail_msg + 'If you want to see all the details, I wrote them to a spreadsheet at ' + spreadsheet_url
            print('Wrote data to Google sheet at URL ' + spreadsheet_url)
        except Exception as e:
            print('Failed to write data to Google sheet: ' + str(e))

        self.slack.send_message(channel, detail_msg)

        # Later, we'll also handle stopped instances which should be terminated


    def execute(self, channel):
        instances = self.aws.list_ec2_instances()

        # Only consider instances which still meet the criteria for stopping, AND were warned earlier today
        instances_to_stop = get_stoppable_instances(instances)
        instances_to_stop = [i for i in instances_to_stop if safe_to_stop(i)]

        if len(instances_to_stop) > 0:
            message = 'I stopped the following instances: '
            for i in instances_to_stop:
                contact = self.slack.lookup_user_by_email(i.contact)
                message = message + make_instance_summary(i) + ', StopAfter={}, MonthlyPrice={}, Contact={}\n' \
                    .format(i.stop_after, money_to_string(i.monthly_price), contact)
                self.aws.stop_instance(i.region_name, i.instance_id)
                self.aws.set_tag(i.region_name, i.instance_id, 'Nagbot State', 'Stopped on ' + TODAY_YYYY_MM_DD)
            self.slack.send_message(channel, message)
        else:
            self.slack.send_message(channel, 'No instances were stopped today.')


def get_stoppable_instances(instances):
    return list(i for i in instances if i.state == 'running' and is_past_date(i.stop_after))


def get_terminatable_instances(instances):
    return list(i for i in instances if i.state == 'stopped' and is_past_date(i.terminate_after))


# Some instances are whitelisted from stop or terminate actions. These won't show up as recommended to stop/terminate.
def is_whitelisted(instance):
    for regex in [r'bam::.*bamboo']:
        if re.fullmatch(regex, instance.name) is not None:
            return True
    return False


# Convert floating point dollars to a readable string
def money_to_string(str):
    return '${:.2f}'.format(str)


# Test whether a string is an ISO-8601 date
def is_date(str):
    return re.fullmatch(r'\d{4}-\d{2}-\d{2}', str) is not None


# Test whether a date has passed
def is_past_date(str):
    if is_date(str):
        return TODAY_YYYY_MM_DD >= str
    elif str == '' or str.lower() == 'on weekends':
        # Unspecified dates default to past. So instances with no "Stop after" tag are eligible for stopping.
        # But any other string like "TBD" or "Never" or a date that we don't understand is NOT considered past.
        return True


def safe_to_stop(instance):
    return instance.state == 'running' and (instance.nagbot_state == 'Stop warning ' + TODAY_YYYY_MM_DD or instance.nagbot_state == 'Stop warning ' + YESTERDAY_YYYY_MM_DD)


def make_instance_summary(instance):
    instance_id = instance.instance_id
    instance_url = url_from_instance_id(instance.region_name, instance_id)
    link = '<{}|{}>'.format(instance_url, instance.name)
    line = '{}, State=({}, "{}"), Type={}'.format(
        link, instance.state, instance.reason, instance.instance_type)
    return line


def url_from_instance_id(region_name, instance_id):
    return 'https://{}.console.aws.amazon.com/ec2/v2/home?region={}#Instances:search={}'.format(region_name, region_name, instance_id)


def main(args):
    """
    Entry point for the application
    """
    channel = args.channel
    mode = args.mode

    if re.fullmatch(r'#[A-Za-z0-9-]+', channel) is None:
        print('Unexpected channel format "%s", should look like #random or #testing' % channel)
        sys.exit(1)
    print('Destination Slack channel is: ' + channel)

    nagbot = Nagbot(sqaws, sqslack)

    if mode.lower() == 'notify':
        nagbot.notify(channel)
    elif mode.lower() == 'execute':
        nagbot.execute(channel)
    else:
        print('Unexpected mode "%s", should be "notify" or "execute"' % mode)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", help="Mode, either 'notify' or 'execute'. "
        "In 'notify' mode, a notification is posted to Slack. "
        "In 'execute' mode, instances are stopped or terminated.")

    parser.add_argument(
        "-c",
        "--channel",
        action="store",
        default='#nagbot-testing',
        help="Which Slack channel to publish to")

    args = parser.parse_args()
    main(args)
