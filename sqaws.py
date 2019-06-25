import os
from dataclasses import dataclass

import awspricing
import boto3

from nagbot import money_to_string

os.environ['AWSPRICING_USE_CACHE'] = '1'
HOURS_IN_A_MONTH = 730

# Quote a string
def quote(str):
    return '"' + str + '"'


# Model class for an EC2 instance
@dataclass
class Instance:
    region_name: str
    instance_id: str
    state: str
    reason: str
    instance_type: str
    name: str
    operating_system: str
    stop_after: str
    terminate_after: str
    contact: str
    nagbot_state: str
    monthly_price: float

    def to_header(self) -> str:
        return ['Instance ID',
                'Name',
                'State',
                'Stop After',
                'Terminate After',
                'Contact',
                'Nagbot State',
                'Monthly Price',
                'Region Name',
                'Instance Type',
                'Reason',
                'OS']

    def to_list(self) -> str:
        return [self.instance_id,
                self.name,
                self.state,
                self.stop_after,
                self.terminate_after,
                self.contact,
                self.nagbot_state,
                money_to_string(self.monthly_price),
                self.region_name,
                self.instance_type,
                self.reason,
                self.operating_system]


# Get a list of model classes representing important properties of EC2 instances
def list_ec2_instances():
    ec2 = boto3.client('ec2', region_name='us-west-2')

    describe_regions_response = ec2.describe_regions()
    instances = []
    i = 1
    print('Checking all AWS regions...')
    for region in describe_regions_response['Regions']:
        print('region = ' + str(region))
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
def build_instance_model(region_name: str, instance_dict: dict) -> Instance:
    instance_type = instance_dict['InstanceType']
    platform = instance_dict.get('Platform', '')
    operating_system = ('Windows' if platform == 'windows' else 'Linux')
    tags = make_tags_dict(instance_dict.get('Tags', []))
    return Instance(region_name=region_name,
                    instance_id=instance_dict['InstanceId'],
                    state=instance_dict['State']['Name'],
                    reason=instance_dict.get('StateTransitionReason', ''),
                    instance_type=instance_type,
                    name=tags.get('Name', ''),
                    operating_system=operating_system,
                    monthly_price=lookup_monthly_price(region_name, instance_type, operating_system),
                    stop_after=tags.get('Stop after', ''),
                    terminate_after=tags.get('Terminate after', ''),
                    contact=tags.get('Contact', ''),
                    nagbot_state=tags.get('Nagbot State', ''));


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


# Set a tag on an instance
def set_tag(region_name, instance_id, tag_name, tag_value):
    ec2 = boto3.client('ec2', region_name=region_name)
    print('Setting tag ' + tag_value + ' on instance: ' + str(instance_id) + " in region " + region_name)
    response = ec2.create_tags(Resources=[instance_id], Tags=[{
        'Key': tag_name,
        'Value': tag_value
    }])
    print('Response from create_tags: ' + str(response))


# Stop an EC2 instance
def stop_instance(region_name, instance_id):
    print('Stopping instance: ' + str(instance_id) + '...')
    ec2 = boto3.client('ec2', region_name=region_name)
    response = ec2.stop_instances(InstanceIds=[instance_id])
    print('Response from stop_instances: ' + str(response))


# Terminate an EC2 instance
def terminate_instance(region_name, instance_id):
    print('Terminating instance: ' + str(instance_id) + '...')
    ec2 = boto3.client('ec2', region_name=region_name)
    response = ec2.terminate_instances(InstanceIds=[instance_id])
    print('Response from terminate_instances: ' + str(response))


if __name__ == '__main__':
    main()
