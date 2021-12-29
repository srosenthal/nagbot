__author__ = "Stephen Rosenthal"
__version__ = "1.7.1"
__license__ = "MIT"

import argparse
import re
import sys
from datetime import datetime, timedelta

from . import gdocs
from . import parsing
from . import sqaws
from . import sqslack
from .sqaws import money_to_string, Instance
from .pricing import PricingData

TERMINATION_WARNING_DAYS = 3

TODAY = datetime.today()
TODAY_YYYY_MM_DD = TODAY.strftime('%Y-%m-%d')
TODAY_IS_WEEKEND = TODAY.weekday() >= 4  # Days are 0-6. 4=Friday, 5=Saturday, 6=Sunday, 0=Monday
YESTERDAY_YYYY_MM_DD = (TODAY - timedelta(days=1)).strftime('%Y-%m-%d')
MIN_TERMINATION_WARNING_YYYY_MM_DD = (TODAY - timedelta(days=3)).strftime('%Y-%m-%d')

"""
PREREQUISITES:
1. An AWS account with credentials set up in a standard place (environment variables, home directory, etc.)
2. The AWS credentials must have access to the EC2 APIs "describe_regions" and "describe_instances"
3. PIP dependencies specified in requirements.txt.
4. Environment variables
   * "SLACK_BOT_TOKEN" containing a token allowing messages to be posted to Slack.
   * "GDOCS_SERVICE_ACCOUNT_FILENAME" containing the name of the google sheet
"""


class Nagbot(object):
    @staticmethod
    def notify_internal(channel, dryrun):
        pricing = PricingData()
        instances = sqaws.list_ec2_instances(pricing)

        num_running_instances = sum(1 for i in instances if i.state == 'running')
        num_total_instances = len(instances)
        running_monthly_cost = money_to_string(sum(i.monthly_price for i in instances))

        summary_msg = "Hi, I'm Nagbot v{} :wink: ".format(__version__)
        summary_msg += "My job is to make sure we don't forget about unwanted AWS servers and waste money!\n"
        summary_msg += "We have {} running EC2 instances right now and {} total.\n".format(num_running_instances,
                                                                                           num_total_instances)
        summary_msg += "If we continue to run these instances all month, it would cost {}.\n" \
            .format(running_monthly_cost)

        # Collect all the data to a Google Sheet
        try:
            header = instances[0].to_header()
            body = [i.to_list() for i in instances]
            spreadsheet_url = gdocs.write_to_spreadsheet([header] + body)
            summary_msg += '\nIf you want to see all the details, I wrote them to a spreadsheet at ' + spreadsheet_url
            print('Wrote data to Google sheet at URL ' + spreadsheet_url)
        except Exception as e:
            print('Failed to write data to Google sheet: ' + str(e))

        sqslack.send_message(channel, summary_msg)

        # From here on, filter out excluded instances
        instances = sorted((i for i in instances if not is_excluded(i)), key=lambda i: i.name)

        instances_to_terminate = get_terminatable_instances(instances)
        if len(instances_to_terminate) > 0:
            terminate_msg = 'The following %d _stopped_ instances are due to be *TERMINATED*, ' \
                            'based on the "Terminate after" tag:\n' % len(instances_to_terminate)
            for i in instances_to_terminate:
                contact = sqslack.lookup_user_by_email(i.contact)
                terminate_msg += make_instance_summary(i) + ', "Terminate after"={}, "Monthly Price"={}, Contact={}\n' \
                    .format(i.terminate_after, money_to_string(i.monthly_price), contact)
                sqaws.set_tag(i.region_name, i.instance_id, 'Terminate after',
                              parsing.add_warning_to_tag(i.terminate_after, TODAY_YYYY_MM_DD), dryrun=dryrun)
        else:
            terminate_msg = 'No instances are due to be terminated at this time.\n'
        sqslack.send_message(channel, terminate_msg)

        instances_to_stop = get_stoppable_instances(instances)
        if len(instances_to_stop) > 0:
            stop_msg = 'The following %d _running_ instances are due to be *STOPPED*, ' \
                       'based on the "Stop after" tag:\n' % len(instances_to_stop)
            for i in instances_to_stop:
                contact = sqslack.lookup_user_by_email(i.contact)
                stop_msg += make_instance_summary(i) + ', "Stop after"={}, "Monthly Price"={}, Contact={}\n' \
                    .format(i.stop_after, money_to_string(i.monthly_price), contact)
                sqaws.set_tag(i.region_name, i.instance_id, 'Stop after',
                              parsing.add_warning_to_tag(i.stop_after, TODAY_YYYY_MM_DD, replace=True), dryrun=dryrun)
        else:
            stop_msg = 'No instances are due to be stopped at this time.\n'
        sqslack.send_message(channel, stop_msg)

    def notify(self, channel, dryrun):
        try:
            self.notify_internal(channel, dryrun)
        except Exception as e:
            sqslack.send_message(channel, "Nagbot failed to run the 'notify' command: " + str(e))
            raise e

    @staticmethod
    def execute_internal(channel, dryrun):
        pricing = PricingData()
        instances = sqaws.list_ec2_instances(pricing)

        # Only terminate instances which still meet the criteria for terminating, AND were warned several times
        instances_to_terminate = get_terminatable_instances(instances)
        instances_to_terminate = [i for i in instances_to_terminate if is_safe_to_terminate(i)]

        # Only stop instances which still meet the criteria for stopping, AND were warned recently
        instances_to_stop = get_stoppable_instances(instances)
        instances_to_stop = [i for i in instances_to_stop if is_safe_to_stop(i)]

        if len(instances_to_terminate) > 0:
            message = 'I terminated the following instances: '
            for i in instances_to_terminate:
                contact = sqslack.lookup_user_by_email(i.contact)
                message = message + make_instance_summary(i) \
                                  + ', "Terminate after"={}, "Monthly Price"={}, Contact={}\n' \
                                    .format(i.terminate_after, money_to_string(i.monthly_price), contact)
                sqaws.terminate_instance(i.region_name, i.instance_id, dryrun=dryrun)
            sqslack.send_message(channel, message)
        else:
            sqslack.send_message(channel, 'No instances were terminated today.')

        if len(instances_to_stop) > 0:
            message = 'I stopped the following instances: '
            for i in instances_to_stop:
                contact = sqslack.lookup_user_by_email(i.contact)
                message = message + make_instance_summary(i) + ', "Stop after"={}, "Monthly Price"={}, Contact={}\n' \
                    .format(i.stop_after, money_to_string(i.monthly_price), contact)
                sqaws.stop_instance(i.region_name, i.instance_id, dryrun=dryrun)
                sqaws.set_tag(i.region_name, i.instance_id, 'Nagbot State', 'Stopped on ' + TODAY_YYYY_MM_DD,
                              dryrun=dryrun)
            sqslack.send_message(channel, message)
        else:
            sqslack.send_message(channel, 'No instances were stopped today.')

    def execute(self, channel, dryrun):
        try:
            self.execute_internal(channel, dryrun)
        except Exception as e:
            sqslack.send_message(channel, "Nagbot failed to run the 'execute' command: " + str(e))
            raise e


def get_stoppable_instances(instances):
    return list(i for i in instances if is_stoppable(i))


def is_stoppable(instance, is_weekend=TODAY_IS_WEEKEND):
    parsed_date: parsing.ParsedDate = parsing.parse_date_tag(instance.stop_after)

    return instance.state == 'running' and (
            # Treat unspecified "Stop after" dates as being in the past
            (parsed_date.expiry_date is None and not parsed_date.on_weekends)
            or (parsed_date.on_weekends and is_weekend)
            or (parsed_date.expiry_date is not None and TODAY_YYYY_MM_DD >= parsed_date.expiry_date))


def get_terminatable_instances(instances):
    return list(i for i in instances if is_terminatable(i))


def is_terminatable(instance):
    parsed_date: parsing.ParsedDate = parsing.parse_date_tag(instance.terminate_after)

    # For now, we'll only terminate instances which have an explicit 'Terminate after' tag
    return instance.state == 'stopped' and (
        (parsed_date.expiry_date is not None and TODAY_YYYY_MM_DD >= parsed_date.expiry_date))


# Some instances are excluded from stop or terminate actions. These won't show up as recommendations to stop/terminate.
def is_excluded(instance: Instance):
    for regex in [r'bam::.*bamboo']:
        if re.fullmatch(regex, instance.name) is not None:
            return True
    if len(instance.eks_nodegroup_name) > 0:
        return True
    return False


def is_safe_to_stop(instance, is_weekend=TODAY_IS_WEEKEND):
    warning_date = parsing.parse_date_tag(instance.stop_after).warning_date
    return is_stoppable(instance, is_weekend=is_weekend) \
        and warning_date is not None and warning_date <= TODAY_YYYY_MM_DD


def is_safe_to_terminate(instance):
    warning_date = parsing.parse_date_tag(instance.terminate_after).warning_date
    return is_terminatable(instance) \
        and warning_date is not None and warning_date <= MIN_TERMINATION_WARNING_YYYY_MM_DD


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
    return 'https://{}.console.aws.amazon.com/ec2/v2/home?region={}#Instances:search={}'.format(region_name,
                                                                                                region_name,
                                                                                                instance_id)


def main(args):
    """
    Entry point for the application
    """
    channel = args.channel
    mode = args.mode
    dryrun = args.dryrun

    if re.fullmatch(r'#[A-Za-z0-9-]+', channel) is None:
        print('Unexpected channel format "%s", should look like #random or #testing' % channel)
        sys.exit(1)
    print('Destination Slack channel is: ' + channel)

    nagbot = Nagbot()

    if mode.lower() == 'notify':
        nagbot.notify(channel, dryrun)
    elif mode.lower() == 'execute':
        nagbot.execute(channel, dryrun)
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

    parser.add_argument(
        "--dryrun",
        action="store_true",
        default=False,
        help="If specified, don't actually take the specified actions")

    parsed_args = parser.parse_args()
    main(parsed_args)
