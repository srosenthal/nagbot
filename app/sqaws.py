from dataclasses import dataclass

import boto3
from .pricing import PricingData


# Convert floating point dollars to a readable string
def money_to_string(amount):
    return '${:.2f}'.format(amount)


# Quote a string
def quote(value):
    return '"' + value + '"'


# Model class for an EC2 instance
@dataclass
class Instance:
    region_name: str
    instance_id: str
    state: str
    reason: str
    instance_type: str
    name: str
    eks_nodegroup_name: str
    operating_system: str
    stop_after: str
    terminate_after: str
    contact: str
    nagbot_state: str
    monthly_price: float
    monthly_server_price: float
    monthly_storage_price: float

    @staticmethod
    def to_header() -> [str]:
        return ['Instance ID',
                'Name',
                'State',
                'Stop After',
                'Terminate After',
                'Contact',
                'Nagbot State',
                'Monthly Price',
                'Monthly Server Price',
                'Monthly Storage Price',
                'Region Name',
                'Instance Type',
                'Reason',
                'OS',
                'EKS Nodegroup']

    def to_list(self) -> [str]:
        return [self.instance_id,
                self.name,
                self.state,
                self.stop_after,
                self.terminate_after,
                self.contact,
                self.nagbot_state,
                money_to_string(self.monthly_price),
                money_to_string(self.monthly_server_price),
                money_to_string(self.monthly_storage_price),
                self.region_name,
                self.instance_type,
                self.reason,
                self.operating_system,
                self.eks_nodegroup_name]


# Get a list of model classes representing important properties of EC2 instances
def list_ec2_instances(pricing: PricingData):
    ec2 = boto3.client('ec2', region_name='us-west-2')

    describe_regions_response = ec2.describe_regions()
    instances = []
    i = 1
    print('Checking all AWS regions...')
    for region in describe_regions_response['Regions']:
        # print('region = ' + str(region))
        region_name = region['RegionName']
        ec2 = boto3.client('ec2', region_name=region_name)
        describe_instances_response = ec2.describe_instances()
        for reservation in describe_instances_response['Reservations']:
            for instance_dict in reservation['Instances']:
                instance = build_instance_model(pricing, region_name, instance_dict)
                instances.append(instance)
                # print(str(i) + ': ' + str(instance))
                i += 1
    return instances


# Get the info about a single EC2 instance
def build_instance_model(pricing: PricingData, region_name: str, instance_dict: dict) -> Instance:
    tags = make_tags_dict(instance_dict.get('Tags', []))

    instance_id = instance_dict['InstanceId']
    state = instance_dict['State']['Name']
    state_reason = instance_dict.get('StateTransitionReason', '')
    instance_type = instance_dict['InstanceType']
    eks_nodegroup_name = tags.get('eks:nodegroup-name', '')
    name = tags.get('Name', eks_nodegroup_name)
    platform = instance_dict.get('Platform', '')
    operating_system = ('Windows' if platform == 'windows' else 'Linux')

    monthly_server_price = pricing.lookup_monthly_price(region_name, instance_type, operating_system)
    monthly_storage_price = estimate_monthly_ebs_storage_price(region_name, instance_dict['InstanceId'])
    monthly_price = (monthly_server_price + monthly_storage_price) if state == 'running' else monthly_storage_price

    stop_after = tags.get('Stop after', tags.get('Stop After', tags.get('StopAfter', '')))
    terminate_after = tags.get('Terminate after', tags.get('Terminate After', tags.get('TerminateAfter', '')))
    contact = tags.get('Contact', '')
    nagbot_state = tags.get('Nagbot State', '')

    return Instance(region_name=region_name,
                    instance_id=instance_id,
                    state=state,
                    reason=state_reason,
                    instance_type=instance_type,
                    eks_nodegroup_name=eks_nodegroup_name,
                    name=name,
                    operating_system=operating_system,
                    monthly_price=monthly_price,
                    monthly_server_price=monthly_server_price,
                    monthly_storage_price=monthly_storage_price,
                    stop_after=stop_after,
                    terminate_after=terminate_after,
                    contact=contact,
                    nagbot_state=nagbot_state)


# Convert the tags list returned from the EC2 API to a dictionary from tag name to tag value
def make_tags_dict(tags_list: list) -> dict:
    tags = dict()
    for tag in tags_list:
        tags[tag['Key']] = tag['Value']
    return tags


# Estimate the monthly cost of an instance's EBS storage (disk drives)
def estimate_monthly_ebs_storage_price(region_name: str, instance_id: str) -> float:
    ec2_resource = boto3.resource('ec2', region_name=region_name)
    total_gb = sum([v.size for v in ec2_resource.Instance(instance_id).volumes.all()])
    return total_gb * 0.1  # Assume EBS costs $0.1/GB/month, true as of Dec 2021 for gp2 type storage


# Set a tag on an instance
def set_tag(region_name: str, instance_id: str, tag_name: str, tag_value: str, dryrun: bool) -> None:
    ec2 = boto3.client('ec2', region_name=region_name)
    print(f'Setting tag {tag_value} on instance: {instance_id} in region {region_name}')
    if not dryrun:
        response = ec2.create_tags(Resources=[instance_id], Tags=[{
            'Key': tag_name,
            'Value': tag_value
        }])
        print(f'Response from create_tags: {str(response)}')


# Stop an EC2 instance
def stop_instance(region_name: str, instance_id: str, dryrun: bool) -> bool:
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


# Terminate an EC2 instance
def terminate_instance(region_name: str, instance_id: str, dryrun: bool) -> bool:
    print(f'Terminating instance: {str(instance_id)}...')
    ec2 = boto3.client('ec2', region_name=region_name)
    try:
        if not dryrun:
            response = ec2.terminate_instances(InstanceIds=[instance_id])
            print(f'Response from terminate_instances: {str(response)}')
        return True
    except Exception as e:
        print(f'Failure when calling terminate_instances: {str(e)}')
        return False
