from dataclasses import dataclass

import boto3
from datetime import datetime, timedelta

from . import parsing

TODAY = datetime.today()
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


# Estimate the monthly cost of an EBS storage volume; pricing estimations based on region us-east-1
def estimate_monthly_ebs_storage_price(region_name: str, instance_id: str, volume_type: str, size: float, iops: float,
                                       throughput: float) -> float:
    if instance_id.startswith('i'):
        ec2_resource = boto3.resource('ec2', region_name=region_name)
        total_gb = sum([v.size for v in ec2_resource.Instance(instance_id).volumes.all()])
        return total_gb * 0.1  # Assume EBS costs $0.1/GB/month when calculating for attached volumes

    if 'gp3' in volume_type:  # gp3 type storage depends on storage, IOPS, and throughput
        cost = size * 0.08
        if iops > 3000:
            provisioned_iops = iops - 3000
            cost = cost + (provisioned_iops * 0.005)
        if throughput > 125:
            provisioned_throughput = throughput - 125
            cost = cost + (provisioned_throughput * 0.04)
        return cost
    else:  # Assume EBS costs $0.1/GB/month, true as of Dec 2021 for gp2 type storage
        return size * 0.1


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
    @staticmethod
    def generic_is_stoppable_without_warning(resource, is_weekend=TODAY_IS_WEEKEND):
        if not resource.ec2_type == 'instance':
            return False
        parsed_date: parsing.ParsedDate = parsing.parse_date_tag(resource.stop_after)
        return resource.state == 'running' and parsed_date.expiry_date is None and \
            ((not parsed_date.on_weekends) or (parsed_date.on_weekends and is_weekend))

    # Check if a resource is stoppable - currently, only instances should be stoppable
    @staticmethod
    def generic_is_stoppable(resource, today_date, is_weekend=TODAY_IS_WEEKEND):
        if not resource.ec2_type == 'instance':
            return False

        parsed_date: parsing.ParsedDate = parsing.parse_date_tag(resource.stop_after)
        return resource.state == 'running' and (
            # Treat unspecified "Stop after" dates as being in the past
            (parsed_date.expiry_date is None and not parsed_date.on_weekends)
            or (parsed_date.on_weekends and is_weekend)
            or (parsed_date.expiry_date is not None and today_date >= parsed_date.expiry_date))

    # Check if a resource is terminatable
    @staticmethod
    def generic_is_terminatable(resource, state, today_date):
        parsed_date: parsing.ParsedDate = parsing.parse_date_tag(resource.terminate_after)

        # For now, we'll only terminate instances which have an explicit 'Terminate after' tag
        return resource.state == state and (
            (parsed_date.expiry_date is not None and today_date >= parsed_date.expiry_date))

    # Check if a resource is safe to stop - currently, only instances should be safe to stop
    @staticmethod
    def generic_is_safe_to_stop(resource, today_date, is_weekend=TODAY_IS_WEEKEND):
        if not resource.ec2_type == 'instance':
            return False

        warning_date = parsing.parse_date_tag(resource.stop_after).warning_date
        return Resource.generic_is_stoppable(resource, today_date, is_weekend=is_weekend) \
            and warning_date is not None and warning_date <= today_date

    # Check if a resource is safe to terminate
    @staticmethod
    def generic_is_safe_to_terminate(resource, resource_type, today_date):
        warning_date = parsing.parse_date_tag(resource.terminate_after).warning_date
        return resource_type.is_terminatable(resource, today_date) and warning_date is not None and warning_date <= \
            MIN_TERMINATION_WARNING_YYYY_MM_DD

    # Create resource summary
    @staticmethod
    def make_generic_resource_summary(resource, resource_type):
        resource_id = resource.resource_id
        resource_url = resource_type.url_from_id(resource.region_name, resource_id)
        link = '<{}|{}>'.format(resource_url, resource.name)
        return link

    # Create resource url
    @staticmethod
    def generic_url_from_id(region_name, resource_id, resource_type):
        return 'https://{}.console.aws.amazon.com/ec2/v2/home?region={}#{}:search={}'.format(region_name, region_name,
                                                                                             resource_type, resource_id)
