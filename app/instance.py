from dataclasses import dataclass

from app import resource
from .resource import Resource
from .volume import estimate_monthly_ebs_storage_price
import boto3
from .pricing import PricingData

from datetime import datetime

TODAY = datetime.today()
TODAY_IS_WEEKEND = TODAY.weekday() >= 4  # Days are 0-6. 4=Friday, 5=Saturday, 6=Sunday, 0=Monday


@dataclass
class Instance(Resource):
    state: str
    ec2_type: str
    monthly_price: float
    monthly_server_price: float
    monthly_storage_price: float
    size: float

    # Return the type and state of the EC2 resource being examined ('instance' and 'running')
    @staticmethod
    def to_string():
        return 'instance', 'running'

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
        return [self.resource_id,
                self.name,
                self.state,
                self.stop_after,
                self.terminate_after,
                self.contact,
                self.nagbot_state,
                resource.money_to_string(self.monthly_price),
                resource.money_to_string(self.monthly_server_price),
                resource.money_to_string(self.monthly_storage_price),
                self.region_name,
                self.resource_type,
                self.reason,
                self.operating_system,
                self.eks_nodegroup_name]

    # Get a list of model classes representing important properties of EC2 instances
    @staticmethod
    def list_resources():
        describe_regions_response = Resource.generic_list_resources()
        instances = []

        for region in describe_regions_response['Regions']:
            region_name = region['RegionName']
            ec2 = boto3.client('ec2', region_name=region_name)
            describe_instances_response = ec2.describe_instances()

            for reservation in describe_instances_response['Reservations']:
                for instance_dict in reservation['Instances']:
                    instance = Instance.build_model(region_name, instance_dict)
                    instances.append(instance)
        return instances

    # Get the info about a single EC2 instance
    @staticmethod
    def build_model(region_name: str, resource_dict: dict):
        tags = resource.make_tags_dict(resource_dict.get('Tags', []))

        state = resource_dict['State']['Name']
        ec2_type = 'instance'

        resource_id_tag = 'InstanceId'
        resource_type_tag = 'InstanceType'
        instance = Resource.build_generic_model(tags, resource_dict, region_name, resource_id_tag, resource_type_tag)

        pricing = PricingData()
        monthly_server_price = pricing.lookup_monthly_price(region_name, instance.resource_type,
                                                            instance.operating_system)
        monthly_storage_price = estimate_monthly_ebs_storage_price(region_name,
                                                                   instance.resource_id, 'none', 0, 0, 0)
        monthly_price = (monthly_server_price + monthly_storage_price) if state == 'running' else monthly_storage_price

        size = 0

        return Instance(region_name=region_name,
                        resource_id=instance.resource_id,
                        state=state,
                        reason=instance.reason,
                        resource_type=instance.resource_type,
                        ec2_type=ec2_type,
                        eks_nodegroup_name=instance.eks_nodegroup_name,
                        name=instance.name,
                        operating_system=instance.operating_system,
                        monthly_price=monthly_price,
                        monthly_server_price=monthly_server_price,
                        monthly_storage_price=monthly_storage_price,
                        stop_after=instance.stop_after,
                        terminate_after=instance.terminate_after,
                        nagbot_state=instance.nagbot_state,
                        contact=instance.contact,
                        stop_after_tag_name=instance.stop_after_tag_name,
                        terminate_after_tag_name=instance.terminate_after_tag_name,
                        nagbot_state_tag_name=instance.nagbot_state_tag_name,
                        size=size,
                        iops=instance.iops,
                        throughput=instance.throughput)

    # Terminate an EC2 instance
    def terminate_resource(self, dryrun: bool) -> bool:
        print(f'Terminating instance: {str(self.resource_id)}...')
        ec2 = boto3.client('ec2', region_name=self.region_name)
        try:
            if not dryrun:
                response = ec2.terminate_instances(InstanceIds=[self.resource_id])
                print(f'Response from terminate_instances: {str(response)}')
            return True
        except Exception as e:
            print(f'Failure when calling terminate_instances: {str(e)}')
            return False

    def is_stoppable_without_warning(self,is_weekend=TODAY_IS_WEEKEND):
        return self.generic_is_stoppable_without_warning(self, is_weekend)

    # Check if an instance is stoppable
    def is_stoppable(self, today_date, is_weekend=TODAY_IS_WEEKEND):
        return self.generic_is_stoppable(self, today_date, is_weekend)

    # Check if an instance is terminatable
    def is_terminatable(self, today_date):
        state = 'stopped'
        return self.generic_is_terminatable(self, state, today_date)

    # Check if an instance is safe to stop
    def is_safe_to_stop(self, today_date, is_weekend=TODAY_IS_WEEKEND):
        return self.generic_is_safe_to_stop(self, today_date, is_weekend)

    # Check if an instance is safe to terminate
    def is_safe_to_terminate(self, today_date):
        resource_type = Instance
        return self.generic_is_safe_to_terminate(self, resource_type, today_date)

    # Check if a instance is active
    def is_active(self):
        return True if self.state == 'running' else False

    # Determine if resource has a 'stopped' state - EC2 Instances do
    @staticmethod
    def can_be_stopped() -> bool:
        return True

    # Create instance summary
    def make_resource_summary(self):
        resource_type = Instance
        link = self.make_generic_resource_summary(self, resource_type)
        if self.reason:
            state = f'State=({self.state}, "{self.reason}")'
        else:
            state = f'State={self.state}'
        line = f'{link}, {state}, Type={self.resource_type}'
        return line

    # Create instance url
    @staticmethod
    def url_from_id(region_name, resource_id):
        resource_type = 'Instances'
        return Resource.generic_url_from_id(region_name, resource_id, resource_type)

    # Include all instances in monthly price calculation
    @staticmethod
    def included_in_monthly_price():
        return True
