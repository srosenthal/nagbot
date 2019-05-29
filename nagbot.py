#!/usr/bin/env python3

import os
import re
import sys
from collections import namedtuple
from datetime import datetime

import awspricing
import boto3
import slack

"""
PREREQUISITES:
1. An AWS account with credentials set up in a standard place (environment variables, home directory, etc.)
2. The AWS credentials must have access to the EC2 APIs "describe_regions" and "describe_instances"
3. PIP dependencies "awspricing", "boto3", "slackclient".
4. Environment variable "SLACK_BOT_TOKEN" containing a token allowing messages to be posted to Slack.
"""

# Cache the queries to the AWS Pricing API
os.environ['AWSPRICING_USE_CACHE'] = '1'

HOURS_IN_A_MONTH = 730
TODAY_YYYY_MM_DD = datetime.today().strftime('%Y-%m-%d')

def main():
    # 1st arg is the program, 2nd is a parameter
    args = sys.argv
    if (len(args) == 2 and str(args[1]).startswith('#')):
        destination_slack_channel = str(args[1])
    else:
        destination_slack_channel = '#nagbot-testing'
    print('Destination Slack channel is: ' + destination_slack_channel)

    instances = list_ec2_instances()
    post_slack_summary_messages(instances, destination_slack_channel)

# Model for an EC2 instance
Instance = namedtuple('Instance', \
                      ['region_name', \
                       'instance_id', \
                       'state', \
                       'reason', \
                       'instance_type', \
                       'name', \
                       'operating_system', \
                       'stop_after', \
                       'terminate_after', \
                       'contact', \
                       'monthly_price'])

# Get a list of model classes representing important properties of EC2 instances
def list_ec2_instances():
    ec2_client = boto3.client('ec2')
    describe_regions_response = ec2_client.describe_regions()
    instances = []
    i = 1
    for region in describe_regions_response['Regions']:
        region_name = region['RegionName']
        ec2_client = boto3.client('ec2', region_name=region_name)
        describe_instances_response = ec2_client.describe_instances()
        for reservation in describe_instances_response['Reservations']:
            for instance_dict in reservation['Instances']:
                instance = build_instance_model(region_name, instance_dict)
                instances.append(instance)
                print(str(i) + ': ' + str(instance))
                i += 1
    return instances

# Post messages to a Slack channel summarizing the status of EC2 instances
def post_slack_summary_messages(instances, destination_slack_channel):
    slack_bot_token = os.environ['SLACK_BOT_TOKEN']
    slack_client = slack.WebClient(token=slack_bot_token)

    num_running_instances = sum(1 for i in instances if i.state == 'running')
    num_total_instances = sum(1 for i in instances)
    running_monthly_cost = money_to_string(sum(i.monthly_price for i in instances if i.state == 'running'))

    # From here on, exclude "whitelisted" instances
    instances = sorted((i for i in instances if not is_whitelisted(i)), key=lambda i: i.name)

    message = "Hi, I'm Nagbot v1.0 :wink: My job is to make sure we don't forget about unwanted AWS servers and waste money!\n"
    message = message + "Here is some data...\n"
    message = message + "We have {} running EC2 instances right now and {} total.\n".format(num_running_instances,
                                                                                            num_total_instances)
    message = message + "If we continue to run these instances all month, it would cost {} (plus more for EBS disks).\n"\
        .format(running_monthly_cost)
    slack_client.chat_postMessage(channel=destination_slack_channel, text=message, as_user=True)
    message = 'The following _running_ instances are due to be *STOPPED*, based on the "Stop after" tag:\n'
    instances_to_stop = list(i for i in instances if i.state == 'running' and is_past_date(i.stop_after))
    for instance in instances_to_stop:
        message = message + make_instance_summary(instance) + ', StopAfter={}, MonthlyPrice={}, Contact={}\n' \
            .format(instance.stop_after, money_to_string(instance.monthly_price), instance.contact)
    slack_client.chat_postMessage(channel=destination_slack_channel, text=message, as_user=True)
    message = 'The following _stopped_ instances are due to be *TERMINATED*, based on the "Terminate after" tag:\n'
    instances_to_terminate = list(i for i in instances if i.state == 'stopped' and is_past_date(i.terminate_after))
    for instance in instances_to_terminate:
        message = message + make_instance_summary(instance) + ', TerminateAfter={}, Contact={}\n' \
            .format(instance.terminate_after, instance.contact)
    slack_client.chat_postMessage(channel=destination_slack_channel, text=message, as_user=True)
    message = 'Stopping and terminating instances are not currently automated, but they might be in the future!'
    slack_client.chat_postMessage(channel=destination_slack_channel, text=message, as_user=True)

# Quote a string
def quote(str):
    return '"' + str + '"'

# Get the info about a single EC2 instance
def build_instance_model(region_name, instance_dict):
    instance_type = instance_dict['InstanceType']
    platform = instance_dict.get('Platform', '')
    operating_system = ('Windows' if platform == 'windows' else 'Linux')
    tags = make_tags_dict(instance_dict['Tags'])
    return Instance(region_name=region_name,
                    instance_id=instance_dict['InstanceId'],
                    state=instance_dict['State']['Name'],
                    reason=instance_dict.get('StateTransitionReason', ''),
                    instance_type=instance_type,
                    name=tags.get('Name', ''),
                    operating_system=operating_system,
                    stop_after=tags.get('Stop after', ''),
                    terminate_after=tags.get('Terminate after', ''),
                    contact=tags.get('Contact', ''),
                    monthly_price=lookup_monthly_price(region_name, instance_type, operating_system));

# Convert the tags list returned from the EC2 API to a dictionary from tag name to tag value
def make_tags_dict(tags_list):
    tags = dict()
    for tag in tags_list:
        tags[tag['Key']] = tag['Value']
    return tags

# Use the AWS API to look up the monthly price of an instance, assuming used all month, as hourly, on-demand
def lookup_monthly_price(region_name, instance_type, operating_system):
    ec2_offer = awspricing.offer('AmazonEC2')
    hourly = ec2_offer.ondemand_hourly(instance_type, region=region_name, operating_system=operating_system)
    return hourly * HOURS_IN_A_MONTH

# Some instances are whitelisted from stop or terminate actions. These won't show up as recommended to stop/terminate.
def is_whitelisted(instance):
    for regex in ['bam::.*bamboo']:
        if re.fullmatch(regex, instance.name) is not None:
            return True
    return False

# Convert floating point dollars to a readable string
def money_to_string(str):
    return '${:.2f}'.format(str)

# Test whether a string is an ISO-8601 date
def is_date(str):
    return re.fullmatch('\d{4}-\d{2}-\d{2}', str) is not None

# Test whether a date has passed
def is_past_date(str):
    if is_date(str):
        return TODAY_YYYY_MM_DD > str;
    elif str == '':
        # Unspecified dates default to past. So instances with no "Stop after" date are eligible for stopping.
        # But any other string like "On weekends" or "Never" or a date that we don't understand is NOT considered past.
        return True

def make_instance_summary(instance):
    instance_id = instance.instance_id
    instance_url = url_from_instance_id(instance.region_name, instance_id)
    link = '<{}|{}>'.format(instance_url, instance.name)
    line = '{}, State=({}, "{}"), Type={}'.format(
        link, instance.state, instance.reason, instance.instance_type)
    return line

def url_from_instance_id(region_name, instance_id):
    return 'https://{}.console.aws.amazon.com/ec2/v2/home?region={}#Instances:search={}'.format(region_name, region_name, instance_id)

if __name__ == "__main__":
    main()