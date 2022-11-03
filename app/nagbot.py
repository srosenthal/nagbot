__author__ = "Stephen Rosenthal"
__version__ = "1.11.1"
__license__ = "MIT"

import argparse
import re
import sys

import app.common_util as util
from . import parsing
from . import sqslack
from .instance import Instance
from .volume import Volume
from .ami import Ami
from .snapshot import Snapshot


RESOURCE_TYPES = [Instance, Ami, Snapshot, Volume]

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
        summary_msg = f"Hi, I'm Nagbot v{__version__} :wink: "
        summary_msg += "My job is to make sure we don't forget about unwanted AWS resources and waste money!\n"

        for resource_type in RESOURCE_TYPES:
            ec2_type, ec2_state = resource_type.to_string()
            resources = resource_type.list_resources()
            num_active_resources = sum(1 for r in resources if r.is_active())
            num_total_resources = len(resources)

            running_monthly_cost = util.money_to_string(sum(r.monthly_price for r in resources
                                                       if r.included_in_monthly_price()))
            summary_msg += f"\n*{resource_type.__name__}s:*\nWe have {num_active_resources} " \
                           f"{ec2_state} {ec2_type}s right now and {num_total_resources} total.\n" \
                           f"If we continue to run these {ec2_type}s all month, it would cost {running_monthly_cost}.\n"

            resources = sorted((r for r in resources if not (len(r.eks_nodegroup_name) > 0)), key=lambda i: i.name)

            resources_to_terminate = (list(r for r in resources if r.can_be_terminated()))
            resources_to_stop = list(r for r in resources if (r.can_be_stopped()))

            if len(resources_to_terminate) > 0:
                summary_msg += f'The following {len(resources_to_terminate)} {ec2_type}s are due to be *TERMINATED*, ' \
                               'based on the "Terminate after" tag:\n'
                for r in resources_to_terminate:
                    contact = sqslack.lookup_user_by_email(r.contact)
                    summary_msg += r.make_resource_summary() + \
                        f', "Terminate after"={r.terminate_after}, "Monthly Price"={util.money_to_string(r.monthly_price)}' \
                        f', Contact={contact}\n'
                    util.set_tag(r.region_name, r.ec2_type, r.resource_id, r.terminate_after_tag_name,
                                            parsing.add_warning_to_tag(r.terminate_after, util.TODAY_YYYY_MM_DD), dryrun=dryrun)
            else:
                summary_msg += f'No {ec2_type}s are due to be terminated at this time.\n'
            # only 'Instance' resource type can be stopped
            if resource_type == 'instance':
                if len(resources_to_stop) > 0:
                    summary_msg += f'The following {len(resources_to_stop)} _{ec2_state}_ {ec2_type}s ' \
                               'are due to be *STOPPED*, based on the "Stop after" tag:\n'
                    for r in resources_to_stop:
                        contact = sqslack.lookup_user_by_email(r.contact)
                        summary_msg += f'{r.make_resource_summary()}, "Stop after"={r.stop_after}, ' \
                                       f'Monthly Price"={util.money_to_string(r.monthly_price)}, Contact={contact}\n'
                        util.set_tag(r.region_name, r.ec2_type, r.resource_id, r.stop_after_tag_name,
                                                parsing.add_warning_to_tag(r.stop_after, util.TODAY_YYYY_MM_DD, replace=True),
                                                dryrun=dryrun)
                else:
                    summary_msg += f'No {ec2_type}s are due to be stopped at this time.\n'
        sqslack.send_message(channel, summary_msg)

    def notify(self, channel, dryrun):
        try:
            self.notify_internal(channel, dryrun)
        except Exception as e:
            sqslack.send_message(channel, f"Nagbot failed to run the 'notify' command: {e}")
            raise e

    @staticmethod
    def execute_internal(channel, dryrun):
        for resource_type in RESOURCE_TYPES:
            ec2_type, ec2_state = resource_type.to_string()
            resources = resource_type.list_resources()

            # Only terminate resources which still meet the criteria for terminating, AND were warned several times
            resources_to_terminate = list(r for r in resources if r.can_be_terminated(util.TODAY_YYYY_MM_DD) and
                                          r.is_safe_to_terminate_after_warning(util.TODAY_YYYY_MM_DD))

            # Only stop resources which still meet the criteria for stopping
            resources_to_stop = list(r for r in resources if (r.is_safe_to_stop()))

            if len(resources_to_terminate) > 0:
                message = f'I terminated the following {ec2_type}s: '
                for r in resources_to_terminate:
                    contact = sqslack.lookup_user_by_email(r.contact)
                    message = message + r.make_resource_summary() + \
                        f', "Terminate after"={r.terminate_after}, "Monthly Price"=' \
                        f'{util.money_to_string(r.monthly_price)}, Contact={contact}\n'
                    r.terminate_resource(dryrun=dryrun)
                sqslack.send_message(channel, message)
            else:
                sqslack.send_message(channel, f'No {ec2_type}s were terminated today.')

            if resource_type == "Instance":
                if len(resources_to_stop) > 0:
                    message = f'I stopped the following {ec2_type}s: '
                    for r in resources_to_stop:
                        contact = sqslack.lookup_user_by_email(r.contact)
                        message = message + r.make_resource_summary() + \
                            f', "Stop after"={r.stop_after}, "Monthly Price"={r.monthly_price}, Contact={contact}\n'
                        util.stop_resource(r.region_name, r.resource_id, dryrun=dryrun)
                        util.set_tag(r.region_name, r.ec2_type, r.resource_id, r.nagbot_state_tag_name,
                                     f'Stopped on {util.TODAY_YYYY_MM_DD}', dryrun=dryrun)
                    sqslack.send_message(channel, message)
                else:
                    sqslack.send_message(channel, f'No {ec2_type}s were stopped today.')

    def execute(self, channel, dryrun):
        try:
            self.execute_internal(channel, dryrun)
        except Exception as e:
            sqslack.send_message(channel, f"Nagbot failed to run the 'execute' command: {str(e)}")
            raise e


def main(args):
    """
    Entry point for the application
    """
    channel = args.channel
    mode = args.mode
    dryrun = args.dryrun

    if re.fullmatch(r'#[A-Za-z\d-]+', channel) is None:
        print(f'Unexpected channel format "{channel}", should look like #random or #testing')
        sys.exit(1)
    print(f'Destination Slack channel is: {channel}')

    nagbot = Nagbot()

    if mode.lower() == 'notify':
        nagbot.notify(channel, dryrun)
    elif mode.lower() == 'execute':
        nagbot.execute(channel, dryrun)
    else:
        print(f'Unexpected mode "{mode}", should be "notify" or "execute"')
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
        default='#bot-testing',
        help="Which Slack channel to publish to")

    parser.add_argument(
        "--dryrun",
        action="store_true",
        default=False,
        help="If specified, don't actually take the specified actions")

    parsed_args = parser.parse_args()
    main(parsed_args)
