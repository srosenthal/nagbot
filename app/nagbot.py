__author__ = "Stephen Rosenthal"
__version__ = "1.8.0"
__license__ = "MIT"

import argparse
import re
import sys
from datetime import datetime

from . import parsing
from . import resource
from . import sqslack
from .resource import money_to_string
from .instance import Instance
from .volume import Volume

TODAY = datetime.today()
TODAY_YYYY_MM_DD = TODAY.strftime('%Y-%m-%d')

RESOURCE_TYPES = [Instance, Volume]

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
        summary_msg = "Hi, I'm Nagbot v{} :wink: ".format(__version__)
        summary_msg += "My job is to make sure we don't forget about unwanted AWS resources and waste money!\n"

        for resource_type in RESOURCE_TYPES:
            ec2_type, ec2_state = resource_type.to_string()
            resources = resource_type.list_resources()
            num_running_resources = sum(1 for r in resources if r.state == 'running' or r.state == 'available')
            num_total_resources = len(resources)

            running_monthly_cost = money_to_string(sum(r.monthly_price for r in resources
                                                       if r.included_in_monthly_price()))
            summary_msg += "\nWe have {} {} {}s right now and {} total.\n".format(num_running_resources, ec2_state,
                                                                                  ec2_type, num_total_resources)
            summary_msg += "If we continue to run these {}s all month, it would cost {}.\n" \
                .format(ec2_type, running_monthly_cost)

            resources = sorted((r for r in resources if not (len(r.eks_nodegroup_name) > 0)), key=lambda i: i.name)

            resources_to_terminate = (list(r for r in resources if r.is_terminatable(TODAY_YYYY_MM_DD)))
            resources_to_stop = list(r for r in resources if r.is_stoppable(today_date=TODAY_YYYY_MM_DD))

            if len(resources_to_terminate) > 0:
                summary_msg += 'The following %d _stopped_ {}s are due to be *TERMINATED*, ' \
                                'based on the "Terminate after" tag:\n'.format(ec2_type) \
                                % len(resources_to_terminate)
                for r in resources_to_terminate:
                    contact = sqslack.lookup_user_by_email(r.contact)
                    summary_msg += r.make_resource_summmary() + \
                        ', "Terminate after"={}, "Monthly Price"={}, Contact={}\n' \
                        .format(r.terminate_after, money_to_string(r.monthly_price), contact)
                    resource.set_tag(r.region_name, r.ec2_type, r.resource_id, r.terminate_after_tag_name,
                                     parsing.add_warning_to_tag(r.terminate_after, TODAY_YYYY_MM_DD), dryrun=dryrun)
            else:
                summary_msg += 'No {}s are due to be terminated at this time.\n' \
                    .format(ec2_type)

            if len(resources_to_stop) > 0:
                summary_msg += 'The following %d _{}_ {}s are due to be *STOPPED*, ' \
                           'based on the "Stop after" tag:\n'.format(ec2_state, ec2_type) \
                           % len(resources_to_stop)
                for r in resources_to_stop:
                    contact = sqslack.lookup_user_by_email(r.contact)
                    summary_msg += r.make_resource_summary() + ', "Stop after"={}, "Monthly Price"={}, Contact={}\n' \
                        .format(r.stop_after, money_to_string(r.monthly_price), contact)
                    resource.set_tag(r.region_name, r.ec2_type, r.resource_id, r.stop_after_tag_name,
                                     parsing.add_warning_to_tag(r.stop_after, TODAY_YYYY_MM_DD, replace=True),
                                     dryrun=dryrun)
            else:
                summary_msg += 'No {}s are due to be stopped at this time.\n'.format(ec2_type)

        sqslack.send_message(channel, summary_msg)

    def notify(self, channel, dryrun):
        try:
            self.notify_internal(channel, dryrun)
        except Exception as e:
            sqslack.send_message(channel, "Nagbot failed to run the 'notify' command: " + str(e))
            raise e

    @staticmethod
    def execute_internal(channel, dryrun):
        for resource_type in RESOURCE_TYPES:
            ec2_type, ec2_state = resource_type.to_string()
            resources = resource_type.list_resources()

            # Only terminate resources which still meet the criteria for terminating, AND were warned several times
            resources_to_terminate = list(r for r in resources if r.is_terminatable(TODAY_YYYY_MM_DD) and
                                          r.is_safe_to_terminate(TODAY_YYYY_MM_DD))

            # Only stop resources which still meet the criteria for stopping, AND were warned recently
            resources_to_stop = list(r for r in resources if r.is_stoppable(today_date=TODAY_YYYY_MM_DD)
                                     and r.is_safe_to_stop(today_date=TODAY_YYYY_MM_DD))

            if len(resources_to_terminate) > 0:
                message = 'I terminated the following {}s: '.format(ec2_type)
                for r in resources_to_terminate:
                    contact = sqslack.lookup_user_by_email(r.contact)
                    message = message + r.make_resource_summary() + \
                        ', "Terminate after"={}, "Monthly Price"={}, Contact={}\n' \
                        .format(r.terminate_after, money_to_string(r.monthly_price), contact)
                    r.terminate_resource(dryrun=dryrun)
                sqslack.send_message(channel, message)
            else:
                sqslack.send_message(channel, 'No {}s were terminated today.'
                                     .format(ec2_type))

            if len(resources_to_stop) > 0:
                message = 'I stopped the following {}s: '.format(ec2_type)
                for r in resources_to_stop:
                    contact = sqslack.lookup_user_by_email(r.contact)
                    message = message + r.make_resource_summary() + \
                        ', "Stop after"={}, "Monthly Price"={}, Contact={}\n' \
                        .format(r.stop_after, money_to_string(r.monthly_price), contact)
                    resource.stop_resource(r.region_name, r.resource_id, dryrun=dryrun)
                    resource.set_tag(r.region_name, r.ec2_type, r.resource_id, r.nagbot_state_tag_name, 'Stopped on '
                                     + TODAY_YYYY_MM_DD, dryrun=dryrun)
                sqslack.send_message(channel, message)
            else:
                sqslack.send_message(channel, 'No {}s were stopped today.'.format(ec2_type))

    def execute(self, channel, dryrun):
        try:
            self.execute_internal(channel, dryrun)
        except Exception as e:
            sqslack.send_message(channel, "Nagbot failed to run the 'execute' command: " + str(e))
            raise e


def main(args):
    """
    Entry point for the application
    """
    channel = args.channel
    mode = args.mode
    dryrun = args.dryrun

    if re.fullmatch(r'#[A-Za-z\d-]+', channel) is None:
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
                     "In 'execute' mode, instances are stopped or terminated and volumes are deleted.")

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
