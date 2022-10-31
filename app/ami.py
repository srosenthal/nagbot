from dataclasses import dataclass

from app import resource
from .resource import Resource
from .snapshot import estimate_monthly_snapshot_price
import boto3
import botocore

from datetime import datetime
TODAY = datetime.today()
TODAY_IS_WEEKEND = TODAY.weekday() >= 4  # Days are 0-6. 4=Friday, 5=Saturday, 6=Sunday, 0=Monday


@dataclass
class Ami(Resource):
    state: str
    ec2_type: str
    monthly_price: float
    volume_type: str
    snapshot_ids: [str]  # list of strings representing ids of each Snapshot making up the AMI

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
                'OS',
                'IOPS',
                'VolumeType'
                'Throughput',
                'Snapshot IDs']

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
                self.volume_type,
                self.throughput,
                self.snapshot_ids]

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

        block_device_mappings = resource_dict['BlockDeviceMappings']
        # Get snapshot id of any Snapshots making up the AMI if there are any
        snapshot_ids = [device['Ebs']['SnapshotId'] for device in block_device_mappings if "Ebs" in device.keys()]
        iops, volume_type = get_ami_iops_and_volume_type(block_device_mappings)
        monthly_price = estimate_monthly_ami_price(ami_type, block_device_mappings, name)

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
                      iops=iops,
                      volume_type=volume_type,
                      throughput=ami.throughput,
                      snapshot_ids=snapshot_ids)

    # Delete/terminate an AMI
    def terminate_resource(self, dryrun: bool) -> bool:
        print(f'Deleting AMI: {str(self.resource_id)} and any Snapshots it is composed of ...')
        ec2 = boto3.resource('ec2', region_name=self.region_name)
        image = ec2.Image(self.resource_id)

        try:
            if not dryrun:
                image.deregister()  # .deregister() returns None
        except Exception as e:
            print(f'Failure when calling image.deregister(): {str(e)}')
            return False

        # Delete Snapshots making up the AMI once the AMI is deleted
        snapshots_deleted = True
        if not dryrun:
            for snapshot_id in self.snapshot_ids:
                snapshot = ec2.Snapshot(snapshot_id)
                print(f"Deleting Snapshot: {snapshot_id}, that was part of AMI: {str(self.resource_id)} ...")
                try:
                    snapshot.delete()  # delete() returns None
                except Exception as e:
                    print(f'Failure when calling snapshot.delete(): {str(e)}')
                    snapshots_deleted = False  # set to False and continue attempting to delete remaining Snapshots
        return snapshots_deleted

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

    # Check if a instance is active
    def is_active(self):
        return self.state == 'available'

    # Determine if resource has a 'stopped' state - AMIs don't
    @staticmethod
    def can_be_stopped() -> bool:
        return False

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


# Not every ami includes iops or volume type (gp2, gp3, standard) so the dictionary is inspected to see if the
# information is available, if it is, that information is returned as a tuple.
def get_ami_iops_and_volume_type(block_device_mappings):
    iops = None
    volume_type = None
    if "Ebs" in block_device_mappings[0].keys():
        if "Iops" in block_device_mappings[0]["Ebs"].keys():
            iops = block_device_mappings[0]['Ebs']['Iops']
        volume_type = block_device_mappings[0]['Ebs']['VolumeType']

    return iops, volume_type


def estimate_monthly_ami_price(ami_type: str, block_device_mappings: list, ami_name: str) -> float:
    total_cost = 0
    # Logic is only implemented for ebs-backed AMIs since Seeq does not use instance-backed AMIs
    if ami_type == 'ebs':
        for device in block_device_mappings:
            # Some AMIs contain block devices which are ephemeral volumes -this is indicative of an instance-backed AMI,
            # but we do not contain any s3 with bundles for AMIs, so these ephemeral volumes should only cost money
            # when an instance is fired up from the AMI, therefore this cost is not included in the sum total.
            if "Ebs" in device.keys():
                snapshot = device["Ebs"]
                snapshot_type = snapshot["VolumeType"]
                snapshot_size = snapshot["VolumeSize"]
                total_cost += estimate_monthly_snapshot_price(snapshot_type, snapshot_size)
    else:
        print(f"WARNING: {ami_name} is a {ami_type} type AMI with the following block_device_mappings: "
              f"{block_device_mappings}")
    return total_cost


def is_ami_registered(ami_id: str) -> bool:
    ec2 = boto3.resource('ec2')
    is_registered = True
    # Retrieve name of AMI, if ClientError or AttributeError is thrown, the AMI does not exist
    try:
        ec2.Image(ami_id).name
    except (botocore.exceptions.ClientError, AttributeError):
        is_registered = False
    return is_registered
