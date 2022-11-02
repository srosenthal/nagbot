from dataclasses import dataclass

import boto3
from datetime import datetime, timedelta

import pytz as pytz

from . import parsing

TODAY = datetime.now(pytz.timezone('US/Pacific'))
TODAY_YYYY_MM_DD = TODAY.strftime('%Y-%m-%d')
TODAY_IS_WEEKEND = TODAY.weekday() >= 4  # Days are 0-6. 4=Friday, 5=Saturday, 6=Sunday, 0=Monday
MIN_TERMINATION_WARNING_YYYY_MM_DD = (TODAY - timedelta(days=3)).strftime('%Y-%m-%d')


# Convert floating point dollars to a readable string
def money_to_string(amount):
    return '${:.2f}'.format(amount)


# Quote a string
def quote(value):
    return '"' + value + '"'


# Convert the tags list returned from the EC2 API to a dictionary from tag name to tag value
def make_tags_dict(tags_list: list) -> dict:
    tags = dict()
    for tag in tags_list:
        tags[tag['Key']] = tag['Value']
    return tags


# Set a tag on an EC2 resource
def set_tag(region_name: str, type_ec2: str, id_name: str, tag_name: str, tag_value: str, dryrun: bool) -> None:
    ec2 = boto3.client('ec2', region_name=region_name)
    print(f'Setting tag {tag_value} on {type_ec2}: {id_name} in region {region_name}')
    if not dryrun:
        response = ec2.create_tags(Resources=[id_name], Tags=[{
            'Key': tag_name,
            'Value': tag_value
        }])
        print(f'Response from create_tags: {str(response)}')


# Get 'stop after', 'terminate after', and 'Nagbot state' tag names in a resource, regardless of formatting
def get_tag_names(tags: dict) -> tuple:
    stop_after_tag_name, terminate_after_tag_name, nagbot_state_tag_name = 'StopAfter', 'TerminateAfter', 'NagbotState'
    for key, value in tags.items():
        if (key.lower()).startswith('stop') and 'after' in (key.lower()):
            stop_after_tag_name = key
        if (key.lower()).startswith('terminate') and 'after' in (key.lower()):
            terminate_after_tag_name = key
        if (key.lower()).startswith('nagbot') and 'state' in (key.lower()):
            nagbot_state_tag_name = key
    return stop_after_tag_name, terminate_after_tag_name, nagbot_state_tag_name


# Stop an EC2 resource - currently, only instances should be able to be stopped
def stop_resource(region_name: str, instance_id: str, dryrun: bool) -> bool:
    print(f'Stopping instance: {str(instance_id)}...')
    ec2 = boto3.client('ec2', region_name=region_name)
    try:
        if not dryrun:
            response = ec2.stop_instances(InstanceIds=[instance_id])
            print(f'Response from stop_instances: {str(response)}')
        return True
    except Exception as e:
        print(f'Failure when calling stop_instances: {str(e)}')
        return False


def has_terminate_after_passed(expiry_date, today_date):
    # For now, we'll only terminate instances which have an explicit 'Terminate after' tag
    return expiry_date is not None and today_date >= expiry_date


# Class representing a generic EC2 resource & containing functions shared by all resources currently in use
@dataclass
class Resource:
    region_name: str
    resource_id: str
    reason: str
    resource_type: str
    name: str
    eks_nodegroup_name: str
    operating_system: str
    stop_after: str
    terminate_after: str
    nagbot_state: str
    contact: str
    stop_after_tag_name: str
    terminate_after_tag_name: str
    nagbot_state_tag_name: str
    iops: float
    throughput: float

    # Get a list of model classes representing important properties of EC2 resources
    @staticmethod
    def generic_list_resources():
        ec2 = boto3.client('ec2', region_name='us-west-2')
        describe_regions_response = ec2.describe_regions()
        print('Checking all AWS regions...')

        return describe_regions_response

    # Get the info about a single EC2 resource
    @staticmethod
    def build_generic_model(tags: dict, resource_dict: dict, region_name: str, resource_id_tag: str,
                            resource_type_tag: str):
        resource_id = resource_dict[resource_id_tag]
        resource_type = resource_dict[resource_type_tag]
        reason = resource_dict.get('StateTransitionReason', '')
        eks_nodegroup_name = tags.get('eks:nodegroup-name', '')
        name = tags.get('Name', eks_nodegroup_name)
        platform = resource_dict.get('Platform', '')
        operating_system = ('Windows' if platform == 'windows' else 'Linux')
        iops = resource_dict.get('Iops', '')
        throughput = resource_dict.get('Throughput', '')

        stop_after_tag_name, terminate_after_tag_name, nagbot_state_tag_name = get_tag_names(tags)
        stop_after = tags.get(stop_after_tag_name, '')
        terminate_after = tags.get(terminate_after_tag_name, '')
        nagbot_state = tags.get(nagbot_state_tag_name, '')
        contact = tags.get('Contact', '')

        return Resource(region_name=region_name,
                        resource_id=resource_id,
                        reason=reason,
                        resource_type=resource_type,
                        eks_nodegroup_name=eks_nodegroup_name,
                        name=name,
                        operating_system=operating_system,
                        stop_after=stop_after,
                        terminate_after=terminate_after,
                        nagbot_state=nagbot_state,
                        contact=contact,
                        stop_after_tag_name=stop_after_tag_name,
                        terminate_after_tag_name=terminate_after_tag_name,
                        nagbot_state_tag_name=nagbot_state_tag_name,
                        iops=iops,
                        throughput=throughput)

    # Instance with no "stop after" date should be stopped without warning
    def is_stoppable_without_warning(self, is_weekend=TODAY_IS_WEEKEND):
        return False

    # Instance with "stop after" date should be stopped after warning period is over
    def is_stoppable_after_warning(self, today_date):
        return False

    # Determine if resource has a 'stopped' state - EC2 Instances do
    # Instance implements its own method to pass True
    def can_be_stopped(self) -> bool:
        return False

    # Check if a resource is safe to terminate
    def is_safe_to_terminate_after_warning(self, today_date):
        parsed_date: parsing.ParsedDate = parsing.parse_date_tag(self.terminate_after)
        warning_date = parsed_date.warning_date
        return has_terminate_after_passed(parsed_date.expiry_date, today_date) \
            and warning_date is not None and warning_date <= MIN_TERMINATION_WARNING_YYYY_MM_DD


    # Create resource summary
    @staticmethod
    def make_generic_resource_summary(resource, resource_type):
        resource_id = resource.resource_id
        resource_url = resource_type.url_from_id(resource.region_name, resource_id)
        link = f'<{resource_url}|{resource.name}>'
        return link

    # Create resource url
    @staticmethod
    def generic_url_from_id(region_name, resource_id, resource_type):
        return f'https://{region_name}.console.aws.amazon.com/ec2/v2/home?region={region_name}#{resource_type}:' \
               f'search={resource_id}'
