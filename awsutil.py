from collections import namedtuple
from datetime import datetime

import awspricing
import boto3

HOURS_IN_A_MONTH = 730

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
    ec2 = boto3.client('ec2')
    describe_regions_response = ec2.describe_regions()
    instances = []
    i = 1
    for region in describe_regions_response['Regions']:
        region_name = region['RegionName']
        ec2 = boto3.client('ec2', region_name=region_name)
        describe_instances_response = ec2.describe_instances()
        for reservation in describe_instances_response['Reservations']:
            for instance_dict in reservation['Instances']:
                instance = build_instance_model(region_name, instance_dict)
                instances.append(instance)
                print(str(i) + ': ' + str(instance))
                i += 1
    return instances

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

def main():
    # Stopping an EC2 instance...
    # stop_instance('us-east-1', 'i-035839cd02a8ba948')

    # Setting a tag on an instance...
    # set_tag('us-east-1', 'i-035839cd02a8ba948', 'Stephen-Test-Tag', 'TAG VALUE HERE')
    1

# Stop an EC2 instance
def stop_instance(region_name, instance_id):
    ec2 = boto3.client('ec2', region_name=region_name)
    response = ec2.stop_instances(InstanceIds=[instance_id])
    print('stop_instances response: ' + str(response))

# Set a tag on an instance
def set_tag(region_name, instance_id, tag_name, tag_value):
    ec2 = boto3.client('ec2', region_name=region_name)
    response = ec2.create_tags(Resources=[instance_id], Tags=[{
        'Key': tag_name,
        'Value': tag_value
    }])
    print('create_tags response: ' + str(response))


if __name__ == '__main__':
    main()