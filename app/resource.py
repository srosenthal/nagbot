from dataclasses import dataclass

import boto3

from . import parsing
import app.common_util as util


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
        stop_after_tag_name, terminate_after_tag_name, nagbot_state_tag_name = util.get_tag_names(tags)
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
    def can_be_stopped(self, is_weekend=util.TODAY_IS_WEEKEND):
        return False

    # Instance with "stop after" date should be stopped after warning period is over
    def is_safe_to_stop(self, today_date):
        return False

    # Default implementation. Individual resources defines the implementation.
    def can_be_terminated(self, today_date=util.TODAY_YYYY_MM_DD):
        return False

    # Check if a resource is safe to terminate
    def is_safe_to_terminate_after_warning(self, today_date):
        parsed_date: parsing.ParsedDate = parsing.parse_date_tag(self.terminate_after)
        warning_date = parsed_date.warning_date
        return util.has_date_passed(parsed_date.expiry_date, today_date) \
            and warning_date is not None and warning_date <= util.MIN_TERMINATION_WARNING_YYYY_MM_DD

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
