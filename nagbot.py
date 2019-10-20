__author__ = "Stephen Rosenthal"
__version__ = "1.5.0"
__license__ = "MIT"

import argparse
import re
import sys
from datetime import datetime, timedelta

import gdocs
import sqaws
import sqslack

TERMINATION_WARNING_DAYS = 3

TODAY = datetime.today()
TODAY_YYYY_MM_DD = TODAY.strftime('%Y-%m-%d')
TODAY_IS_WEEKEND = TODAY.weekday() >= 4  # Days are 0-6. 4=Friday, 5=Saturday, 6=Sunday, 0=Monday
YESTERDAY_YYYY_MM_DD = (TODAY - timedelta(days=1)).strftime('%Y-%m-%d')


"""
PREREQUISITES:
1. An AWS account with credentials set up in a standard place (environment variables, home directory, etc.)
2. The AWS credentials must have access to the EC2 APIs "describe_regions" and "describe_instances"
3. PIP dependencies specified in requirements.txt.
4. Environment variable "SLACK_BOT_TOKEN" containing a token allowing messages to be posted to Slack.
"""


class Nagbot(object):

    def __init__(self, aws, slack):
        self.aws = aws
        self.slack = slack


    def notify_internal(self, channel):
        instances = self.aws.list_ec2_instances()

        num_running_instances = sum(1 for i in instances if i.state == 'running')
        num_total_instances = sum(1 for i in instances)
        running_monthly_cost = money_to_string(sum(i.monthly_price for i in instances))

        summary_msg = "Hi, I'm Nagbot v{} :wink: My job is to make sure we don't forget about unwanted AWS servers and waste money!\n".format(__version__)
        summary_msg += "We have {} running EC2 instances right now and {} total.\n".format(num_running_instances,
                                                                                                num_total_instances)
        summary_msg += "If we continue to run these instances all month, it would cost {}.\n" \
            .format(running_monthly_cost)

        # Collect all of the data to a Google Sheet
        try:
            header = instances[0].to_header()
            body = [i.to_list() for i in instances]
            spreadsheet_url = gdocs.write_to_spreadsheet([header] + body)
            summary_msg += '\nIf you want to see all the details, I wrote them to a spreadsheet at ' + spreadsheet_url
            print('Wrote data to Google sheet at URL ' + spreadsheet_url)
        except Exception as e:
            print('Failed to write data to Google sheet: ' + str(e))

        self.slack.send_message(channel, summary_msg)

        # From here on, exclude "whitelisted" instances
        all_instances = instances
        instances = sorted((i for i in instances if not is_whitelisted(i)), key=lambda i: i.name)

        instances_to_terminate = get_terminatable_instances(instances)
        if len(instances_to_terminate) > 0:
            terminate_msg = 'The following %d _running_ instances are due to be *TERMINATED*, based on the "Terminate After" tag:\n' % len(instances_to_terminate)
            for i in instances_to_terminate:
                contact = self.slack.lookup_user_by_email(i.contact)
                terminate_msg += make_instance_summary(i) + ', "Terminate After"={}, "Monthly Price"={}, Contact={}\n' \
                    .format(i.terminate_after, money_to_string(i.monthly_price), contact)
                self.aws.set_tag(i.region_name, i.instance_id, 'Nagbot State', 'Terminate warning ' + TODAY_YYYY_MM_DD)
        else:
            terminate_msg = 'No instances are due to be terminated at this time.\n'
        self.slack.send_message(channel, terminate_msg)

        instances_to_stop = get_stoppable_instances(instances)
        if len(instances_to_stop) > 0:
            stop_msg ='The following %d _stopped_ instances are due to be *STOPPED*, based on the "Stop After" tag:\n' % len(instances_to_stop)
            for i in instances_to_stop:
                contact = self.slack.lookup_user_by_email(i.contact)
                stop_msg += make_instance_summary(i) + ', "Stop After"={}, "Monthly Price"={}, Contact={}\n' \
                    .format(i.stop_after, money_to_string(i.monthly_price), contact)
                self.aws.set_tag(i.region_name, i.instance_id, 'Nagbot State', 'Stop warning ' + TODAY_YYYY_MM_DD)
        else:
            stop_msg = 'No instances are due to be stopped at this time.\n'
        self.slack.send_message(channel, stop_msg)


    def notify(self, channel):
        try:
            self.notify_internal(channel)
        except Exception as e:
            self.slack.send_message(channel, "Nagbot failed to run the 'notify' command: " + str(e))
            raise(e)


    def execute_internal(self, channel):
        instances = self.aws.list_ec2_instances()

        # Only terminate instances which still meet the criteria for terminating, AND were warned several times
        instances_to_terminate = get_terminatable_instances(instances)
        instances_to_terminate = [i for i in instances_to_terminate if is_safe_to_terminate(i)]

        # Only stop instances which still meet the criteria for stopping, AND were warned recently
        instances_to_stop = get_stoppable_instances(instances)
        instances_to_stop = [i for i in instances_to_stop if is_safe_to_stop(i)]

        if len(instances_to_terminate) > 0:
            message = 'I terminated the following instances: '
            for i in instances_to_terminate:
                contact = self.slack.lookup_user_by_email(i.contact)
                message = message + make_instance_summary(i) + ', "Terminate After"={}, "Monthly Price"={}, Contact={}\n' \
                    .format(i.terminate_after, money_to_string(i.monthly_price), contact)
                self.aws.terminate_instance(i.region_name, i.instance_id)
            self.slack.send_message(channel, message)
        else:
            self.slack.send_message(channel, 'No instances were terminated today.')

        if len(instances_to_stop) > 0:
            message = 'I stopped the following instances: '
            for i in instances_to_stop:
                contact = self.slack.lookup_user_by_email(i.contact)
                message = message + make_instance_summary(i) + ', "Stop After"={}, "Monthly Price"={}, Contact={}\n' \
                    .format(i.stop_after, money_to_string(i.monthly_price), contact)
                self.aws.stop_instance(i.region_name, i.instance_id)
                self.aws.set_tag(i.region_name, i.instance_id, 'Nagbot State', 'Stopped on ' + TODAY_YYYY_MM_DD)
            self.slack.send_message(channel, message)
        else:
            self.slack.send_message(channel, 'No instances were stopped today.')


    def execute(self, channel):
        try:
            self.execute_internal(channel)
        except Exception as e:
            self.slack.send_message(channel, "Nagbot failed to run the 'execute' command: " + str(e))
            raise(e)


def get_stoppable_instances(instances):
    return list(i for i in instances if is_stoppable(i))


def is_stoppable(instance):
    return instance.state == 'running' and is_past_date(instance.stop_after)


def get_terminatable_instances(instances):
    return list(i for i in instances if is_terminatable(i))


def is_terminatable(instance):
    # For now, we'll only terminate instances which have an explicit 'Terminate After' tag
    return instance.state == 'stopped' and instance.terminate_after and is_past_date(instance.terminate_after)


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
    elif str == '':
        # Instances with empty "Stop After" or "Terminate After" are treated as past dates,
        # so they are eligible for stopping or termination.
        return True
    elif TODAY_IS_WEEKEND and (str.lower() == 'on weekends' or str.lower() == 'onweekends'):
        # Instances with special case tag "On Weekends" will be stopped on Friday, Saturday, Sunday
        return True
    else:
        # Any other string like "TBD" or "Never" or a date format that we don't understand is NOT considered past.
        return False


def is_safe_to_stop(instance):
    return instance.state == 'running' and (instance.nagbot_state == 'Stop warning ' + TODAY_YYYY_MM_DD or instance.nagbot_state == 'Stop warning ' + YESTERDAY_YYYY_MM_DD)


def is_safe_to_terminate(instance):
    is_stopped = instance.state == 'stopped'

    match = re.fullmatch(r'Terminate warning (\d{4}-\d{2}-\d{2})', instance.nagbot_state)
    if match:
        warning_date = datetime.strptime(m.group(1), '%Y-%m-%d')
        return is_stopped and (TODAY - warning_date).days > TERMINATION_WARNING_DAYS

    return False


def make_instance_summary(instance):
    instance_id = instance.instance_id
    instance_url = url_from_instance_id(instance.region_name, instance_id)
    link = '<{}|{}>'.format(instance_url, instance.name)
    if instance.reason:
        state = 'State=({}, "{}")'.format(instance.state, instance.reason)
    else:
        state = 'State={}'.format(instance.state)
    line = '{}, {}, Type={}'.format(link, state, instance.instance_type)
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
