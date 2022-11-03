from dataclasses import dataclass

import app.common_util as util
from app import parsing
from .resource import Resource
import boto3

from datetime import datetime

TODAY = datetime.today()
TODAY_IS_WEEKEND = TODAY.weekday() >= 4  # Days are 0-6. 4=Friday, 5=Saturday, 6=Sunday, 0=Monday


@dataclass
class Volume(Resource):
    state: str
    ec2_type: str
    monthly_price: float
    monthly_server_price: float
    monthly_storage_price: float
    size: float

    # Return the type and state of the EC2 resource being examined ('volume' and 'unattached')
    @staticmethod
    def to_string():
        return 'volume', 'unattached'

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
                'OS',
                'Size',
                'IOPS',
                'Throughput']

    def to_list(self) -> [str]:
        return [self.resource_id,
                self.name,
                self.state,
                self.terminate_after,
                self.contact,
                self.monthly_price,
                self.region_name,
                self.resource_type,
                self.operating_system,
                self.size,
                self.iops,
                self.throughput]

    # Get a list of model classes representing important properties of EBS volumes
    @staticmethod
    def list_resources():
        describe_regions_response = Resource.generic_list_resources()
        volumes = []

        for region in describe_regions_response['Regions']:
            region_name = region['RegionName']
            ec2 = boto3.client('ec2', region_name=region_name)
            describe_volumes_response = ec2.describe_volumes()

            for volume_dict in describe_volumes_response['Volumes']:
                volume = Volume.build_model(region_name, volume_dict)
                volumes.append(volume)
        return volumes

    # Get the info about a single EBS volume
    @staticmethod
    def build_model(region_name: str, resource_dict: dict):
        tags = util.make_tags_dict(resource_dict.get('Tags', []))

        state = resource_dict['State']
        ec2_type = 'volume'
        size = resource_dict['Size']

        resource_id_tag = 'VolumeId'
        resource_type_tag = 'VolumeType'
        volume = Resource.build_generic_model(tags, resource_dict, region_name, resource_id_tag, resource_type_tag)

        monthly_price = estimate_monthly_ebs_storage_price(region_name, volume.resource_id,
                                                           volume.resource_type, size, volume.iops,
                                                           volume.throughput)
        monthly_server_price, monthly_storage_price = 0, 0

        return Volume(region_name=region_name,
                      resource_id=volume.resource_id,
                      state=state,
                      reason=volume.reason,
                      resource_type=volume.resource_type,
                      ec2_type=ec2_type,
                      eks_nodegroup_name=volume.eks_nodegroup_name,
                      name=volume.name,
                      operating_system=volume.operating_system,
                      monthly_price=monthly_price,
                      monthly_server_price=monthly_server_price,
                      monthly_storage_price=monthly_storage_price,
                      stop_after=volume.stop_after,
                      terminate_after=volume.terminate_after,
                      nagbot_state=volume.nagbot_state,
                      contact=volume.contact,
                      stop_after_tag_name=volume.stop_after_tag_name,
                      terminate_after_tag_name=volume.terminate_after_tag_name,
                      nagbot_state_tag_name=volume.nagbot_state_tag_name,
                      size=size,
                      iops=volume.iops,
                      throughput=volume.throughput)

    # Delete/terminate an EBS volume
    def terminate_resource(self, dryrun: bool) -> bool:
        print(f'Deleting volume: {str(self.resource_id)}...')
        ec2 = boto3.client('ec2', region_name=self.region_name)
        try:
            if not dryrun:
                response = ec2.delete_volume(VolumeId=self.resource_id)
                print(f'Response from delete_volumes: {str(response)}')
            return True
        except Exception as e:
            print(f'Failure when calling delete_volumes: {str(e)}')
            return False

    # Check if a volume is deletable/terminatable without warning
    def can_be_terminated(self, today_date=util.TODAY_YYYY_MM_DD):
        parsed_date: parsing.ParsedDate = parsing.parse_date_tag(self.terminate_after)
        return self.state == 'available' and util.has_date_passed(parsed_date.expiry_date, today_date)

    # Check if a volume is safe to delete/terminate - warning period has passed
    def is_safe_to_terminate_after_warning(self, today_date):
        return self.state == 'available' and super().is_safe_to_terminate_after_warning(today_date)

    # Check if a volume is active
    def is_active(self):
        return True if self.state == 'available' else False

    # Create volume summary
    def make_resource_summary(self):
        resource_type = Volume
        link = self.make_generic_resource_summary(self, resource_type)
        state = f'State={self.state}'
        line = f'{link}, {state}, Type={resource_type}'
        return line

    # Create volume url
    @staticmethod
    def url_from_id(region_name, resource_id):
        resource_type = 'Volumes'
        return Resource.generic_url_from_id(region_name, resource_id, resource_type)

    # Include volume in monthly price calculation if available
    def included_in_monthly_price(self):
        if self.state == 'available':
            return True
        else:
            return False


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
