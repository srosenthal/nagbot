from dataclasses import dataclass

from app import resource
from .resource import Resource
import boto3

from datetime import datetime
TODAY = datetime.today()
TODAY_IS_WEEKEND = TODAY.weekday() >= 4  # Days are 0-6. 4=Friday, 5=Saturday, 6=Sunday, 0=Monday


@dataclass
class Ami(Resource):
    state: str
    ec2_type: str
    monthly_price: float

    # Return the type and state of the AMI
    @staticmethod
    def to_string():
        return 'ami', 'available'

    @staticmethod
    def to_header() -> [str]:
        return ['AMI ID',
                'Name',
                'State',
                'Terminate After',
                'Contact',
                'Monthly Price',
                'Region Name',
                'AMI Type',
                'OS'
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
                self.iops,
                self.throughput]

    # Get a list of model classes representing important properties of AMIs
    @staticmethod
    def list_resources():
        describe_regions_response = Resource.generic_list_resources()

        amis = []

        for region in describe_regions_response['Regions']:
            region_name = region['RegionName']
            ec2 = boto3.client('ec2', region_name=region_name)
            describe_images_response = ec2.describe_images(Owners=['self'])

            for ami_dict in describe_images_response['Images']:
                ami = Ami.build_model(region_name, ami_dict)
                amis.append(ami)
        return amis

    # Get the info about a single AMI
    @staticmethod
    def build_model(region_name: str, resource_dict: dict):
        tags = resource.make_tags_dict(resource_dict.get('Tags', []))

        state = resource_dict['State']
        ec2_type = 'ami'

        resource_id_tag = 'ImageId'
        resource_type_tag = 'ImageType'
        name = resource_dict[resource_id_tag]
        ami = Resource.build_generic_model(tags, resource_dict, region_name, resource_id_tag, resource_type_tag)
        ami_type = resource_dict['RootDeviceType']  # either instance-store or ebs
        block_device_mappings = resource_dict['BlockDeviceMappings']  # the collection of ebs snapshots forming the ami

        monthly_price = resource.estimate_monthly_ami_price(ami_type, block_device_mappings, name)
        print(monthly_price)

        return Ami(region_name=region_name,
                      resource_id=ami.resource_id,
                      state=state,
                      reason=ami.reason,
                      resource_type=ami.resource_type,
                      ec2_type=ec2_type,
                      eks_nodegroup_name=ami.eks_nodegroup_name,
                      name=ami.name,
                      operating_system=ami.operating_system,
                      monthly_price=monthly_price,
                      stop_after=ami.stop_after,
                      terminate_after=ami.terminate_after,
                      nagbot_state=ami.nagbot_state,
                      contact=ami.contact,
                      stop_after_tag_name=ami.stop_after_tag_name,
                      terminate_after_tag_name=ami.terminate_after_tag_name,
                      nagbot_state_tag_name=ami.nagbot_state_tag_name,
                      iops=ami.iops,
                      throughput=ami.throughput)

    # Delete/terminate an AMI
    def terminate_resource(self, dryrun: bool) -> bool:
        print(f'Deleting AMI: {str(self.resource_id)}...')
        ec2 = boto3.resource('ec2', region_name=self.region_name)
        image = ec2.Image(self.resource_id)
        try:
            if not dryrun:
                response = image.deregister()  # response should return None
                print(f'Response from image.deregister() (should be None): {str(response)}')
            return True
        except Exception as e:
            print(f'Failure when calling image.deregister(): {str(e)}')
            return False

    def is_stoppable_without_warning(self):
        return self.generic_is_stoppable_without_warning(self)

    # Check if an ami is stoppable (should always be false)
    def is_stoppable(self, today_date, is_weekend=TODAY_IS_WEEKEND):
        return self.generic_is_stoppable(self, today_date, is_weekend)

    # Check if an ami is deletable/terminatable
    def is_terminatable(self, today_date):
        state = 'available'
        return self.generic_is_terminatable(self, state, today_date)

    # Check if an ami is safe to stop (should always be false)
    def is_safe_to_stop(self, today_date, is_weekend=TODAY_IS_WEEKEND):
        return self.generic_is_safe_to_stop(self, today_date, is_weekend)

    # Check if an ami is safe to delete/terminate
    def is_safe_to_terminate(self, today_date):
        resource_type = Ami
        return self.generic_is_safe_to_terminate(self, resource_type, today_date)

    # Create ami summary
    def make_resource_summary(self):
        resource_type = Ami
        link = self.make_generic_resource_summary(self, resource_type)
        state = f'State={self.state}'
        line = f'{link}, {state}, Type={self.resource_type}'
        return line

    # Create ami url
    @staticmethod
    def url_from_id(region_name, resource_id):
        resource_type = 'Amis'
        return Resource.generic_url_from_id(region_name, resource_id, resource_type)

    # Include ami in monthly price calculation if available
    def included_in_monthly_price(self):
        if self.state == 'available':
            return True
        else:
            return False
