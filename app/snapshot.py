from dataclasses import dataclass

from app import resource
from .resource import Resource
import boto3

from datetime import datetime

TODAY = datetime.today()
TODAY_IS_WEEKEND = TODAY.weekday() >= 4  # Days are 0-6. 4=Friday, 5=Saturday, 6=Sunday, 0=Monday


@dataclass
class Snapshot(Resource):
    state: str
    ec2_type: str
    monthly_price: float
    size: float

    # Return the type and state of the Snapshot
    @staticmethod
    def to_string():
        return 'snapshot', 'completed'

    @staticmethod
    def to_header() -> [str]:
        return ['Snapshot ID',
                'Name',
                'State',
                'Terminate After',
                'Contact',
                'Monthly Price',
                'Region Name',
                'Snapshot Type',
                'OS'
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

    # Get a list of model classes representing important properties of snapshots
    @staticmethod
    def list_resources():
        describe_regions_response = Resource.generic_list_resources()

        snapshots = []

        for region in describe_regions_response['Regions']:
            region_name = region['RegionName']
            ec2 = boto3.client('ec2', region_name=region_name)
            describe_snapshots_response = ec2.describe_snapshots(OwnerIds=["self"])

            for snapshot_dict in describe_snapshots_response['Snapshots']:
                snapshot = Snapshot.build_model(region_name, snapshot_dict)
                snapshots.append(snapshot)
        return snapshots

    @staticmethod
    def build_model(region_name: str, resource_dict: dict):
        tags = resource.make_tags_dict(resource_dict.get('Tags', []))
        state = resource_dict['State']
        ec2_type = 'snapshot'
        size = resource_dict['VolumeSize']
        snapshot_type = resource_dict['StorageTier']
        resource_id_tag = 'SnapshotId'
        resource_type_tag = 'StorageTier'
        monthly_price = resource.estimate_monthly_snapshot_price(snapshot_type, size)

        snapshot = Resource.build_generic_model(tags, resource_dict, region_name, resource_id_tag, resource_type_tag)

        return Snapshot(region_name=region_name,
                   resource_id=snapshot.resource_id,
                   state=state,
                   reason=snapshot.reason,
                   resource_type=snapshot.resource_type,
                   ec2_type=ec2_type,
                   eks_nodegroup_name=snapshot.eks_nodegroup_name,
                   name=snapshot.name,
                   operating_system=snapshot.operating_system,
                   monthly_price=monthly_price,
                   stop_after=snapshot.stop_after,
                   terminate_after=snapshot.terminate_after,
                   nagbot_state=snapshot.nagbot_state,
                   contact=snapshot.contact,
                   stop_after_tag_name=snapshot.stop_after_tag_name,
                   terminate_after_tag_name=snapshot.terminate_after_tag_name,
                   nagbot_state_tag_name=snapshot.nagbot_state_tag_name,
                   size=size,
                   iops=snapshot.iops,
                   throughput=snapshot.throughput)

    def terminate_resource(self, dryrun: bool) -> bool:
        print(f'Deleting snapshot: {str(self.resource_id)}...')
        ec2 = boto3.client('ec2', region_name=self.region_name)
        snapshot = ec2.Snapshot(self.resource_id)
        try:
            if not dryrun:
                response = snapshot.delete()
                print(f'Response from snapshot.delete(): {str(response)}')
            return True
        except Exception as e:
            print(f'Failure when calling snapshot.delete(): {str(e)}')
            return False

    def is_stoppable_without_warning(self):
        return self.generic_is_stoppable_without_warning(self)

    # Check if a snapshot is stoppable (should always be false)
    def is_stoppable(self, today_date, is_weekend=TODAY_IS_WEEKEND):
        return self.generic_is_stoppable(self, today_date, is_weekend)

    # Check if a snapshot is deletable/terminatable
    def is_terminatable(self, today_date):
        state = 'completed'
        return self.generic_is_terminatable(self, state, today_date)

    # Check if a snapshot is safe to stop (should always be false)
    def is_safe_to_stop(self, today_date, is_weekend=TODAY_IS_WEEKEND):
        return self.generic_is_safe_to_stop(self, today_date, is_weekend)

    # Check if a snapshot is safe to delete/terminate
    def is_safe_to_terminate(self, today_date):
        resource_type = Snapshot
        return self.generic_is_safe_to_terminate(self, resource_type, today_date)

    # Create snapshot summary
    def make_resource_summary(self):
        resource_type = Snapshot
        link = self.make_generic_resource_summary(self, resource_type)
        state = f'State={self.state}'
        line = f'{link}, {state}, Type={self.resource_type}'
        return line

    # Create snapshot url
    @staticmethod
    def url_from_id(region_name, resource_id):
        resource_type = 'Snapshots'
        return Resource.generic_url_from_id(region_name, resource_id, resource_type)

    # Include snapshot in monthly price calculation if available
    def included_in_monthly_price(self):
        if self.state == 'completed':
            return True
        else:
            return False
