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
    stop_after_tag_name: str
    terminate_after_tag_name: str
    nagbot_state_tag_name: str

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


@dataclass
class Volume:
    region_name: str
    volume_id: str
    state: str
    volume_type: str
    size: float
    iops: float
    throughput: float
    name: str
    operating_system: str
    terminate_after: str
    contact: str
    monthly_price: float
    terminate_after_tag_name: str

    @staticmethod
    def to_header() -> [str]:
        return ['Volume ID',
                'Name',
                'State',
                'Terminate After',
                'Contact',
                'Monthly Price',
                'Region Name',
                'Volume Type',
                'OS'
                'Size',
                'IOPS',
                'Throughput']

    def to_list(self) -> [str]:
        return [self.volume_id,
                self.name,
                self.state,
                self.terminate_after,
                self.contact,
                self.monthly_price,
                self.region_name,
                self.volume_type,
                self.operating_system,
                self.size,
                self.iops,
                self.throughput]


# Get a list of model classes representing important properties of EC2 resources
def list_ec2_resources(pricing: PricingData) -> tuple:
    ec2 = boto3.client('ec2', region_name='us-west-2')

    describe_regions_response = ec2.describe_regions()
    instances = []
    volumes = []

    print('Checking all AWS regions...')
    for region in describe_regions_response['Regions']:
        region_name = region['RegionName']
        ec2 = boto3.client('ec2', region_name=region_name)

        describe_instances_response = ec2.describe_instances()
        describe_volumes_response = ec2.describe_volumes()

        for reservation in describe_instances_response['Reservations']:
            for instance_dict in reservation['Instances']:
                instance = build_instance_model(pricing, region_name, instance_dict)
                instances.append(instance)

        for volume_dict in describe_volumes_response['Volumes']:
            volume = build_volume_model(region_name, volume_dict)
            volumes.append(volume)

    return instances, volumes


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
    monthly_storage_price = estimate_monthly_volume_price(region_name, instance_dict['InstanceId'], 'none', 0, 0, 0)
    monthly_price = (monthly_server_price + monthly_storage_price) if state == 'running' else monthly_storage_price

    stop_after_tag_name, terminate_after_tag_name, nagbot_state_tag_name = get_tag_names(tags)
    stop_after = tags.get(stop_after_tag_name, '')
    terminate_after = tags.get(terminate_after_tag_name, '')
    contact = tags.get('Contact', '')
    nagbot_state = tags.get(nagbot_state_tag_name, '')

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
                    nagbot_state=nagbot_state,
                    stop_after_tag_name=stop_after_tag_name,
                    terminate_after_tag_name=terminate_after_tag_name,
                    nagbot_state_tag_name=nagbot_state_tag_name)


# Get the info about a single EBS volume
def build_volume_model(region_name: str, volume_dict: dict) -> Volume:
    tags = make_tags_dict(volume_dict.get('Tags', []))

    volume_id = volume_dict['VolumeId']
    state = volume_dict['State']
    volume_type = volume_dict['VolumeType']
    name = tags.get('Name', '')
    platform = volume_dict.get('Platform', '')
    operating_system = ('Windows' if platform == 'windows' else 'Linux')
    size = volume_dict['Size']
    iops = volume_dict.get('Iops', '')
    throughput = volume_dict.get('Throughput', '')

    monthly_price = estimate_monthly_volume_price(region_name, volume_id, volume_type, size, iops, throughput)

    terminate_after_tag_name = 'TerminateAfter'
    for key, value in tags.items():
        if (key.lower()).startswith('terminate') and 'after' in (key.lower()):
            terminate_after_tag_name = key
    terminate_after = tags.get(terminate_after_tag_name, '')
    contact = tags.get('Contact', '')

    return Volume(region_name=region_name,
                  volume_id=volume_id,
                  state=state,
                  volume_type=volume_type,
                  name=name,
                  operating_system=operating_system,
                  monthly_price=monthly_price,
                  terminate_after=terminate_after,
                  contact=contact,
                  terminate_after_tag_name=terminate_after_tag_name,
                  size=size,
                  iops=iops,
                  throughput=throughput)


# Get 'stop after', 'terminate after', and 'Nagbot state' tag names in an EC2 instance, regardless of formatting
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


# Estimate the monthly cost of an EBS storage volume; pricing estimations based on region us-east-1
def estimate_monthly_volume_price(region_name: str, instance_id: str, volume_type: str, size: float, iops: float,
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


# Set a tag
def set_tag(region_name: str, type_ec2: str, id_name: str, tag_name: str, tag_value: str, dryrun: bool) -> None:
    ec2 = boto3.client('ec2', region_name=region_name)
    print(f'Setting tag {tag_value} on {type_ec2}: {id_name} in region {region_name}')
    if not dryrun:
        response = ec2.create_tags(Resources=[id_name], Tags=[{
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


# Delete an EBS volume
def delete_volume(region_name: str, volume_id: str, dryrun: bool) -> bool:
    print(f'Deleting volume: {str(volume_id)}...')
    ec2 = boto3.client('ec2', region_name=region_name)
    try:
        if not dryrun:
            response = ec2.delete_volume(VolumeId=volume_id)
            print(f'Response from delete_volumes: {str(response)}')
        return True
    except Exception as e:
        print(f'Failure when calling delete_volumes: {str(e)}')
        return False
