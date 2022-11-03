from datetime import datetime, timedelta

import boto3
import pytz as pytz


TODAY = datetime.now(pytz.timezone('US/Pacific'))
TODAY_YYYY_MM_DD = TODAY.strftime('%Y-%m-%d')
TODAY_IS_WEEKEND = TODAY.weekday() >= 4  # Days are 0-6. 4=Friday, 5=Saturday, 6=Sunday, 0=Monday
MIN_TERMINATION_WARNING_YYYY_MM_DD = (TODAY - timedelta(days=3)).strftime('%Y-%m-%d')


def money_to_string(amount):
    return '${:.2f}'.format(amount)


def quote(value):
    return '"' + value + '"'


def make_tags_dict(tags_list: list) -> dict:
    tags = dict()
    for tag in tags_list:
        tags[tag['Key']] = tag['Value']
    return tags


def set_tag(region_name: str, type_ec2: str, id_name: str, tag_name: str, tag_value: str, dryrun: bool) -> None:
    ec2 = boto3.client('ec2', region_name=region_name)
    print(f'Setting tag {tag_value} on {type_ec2}: {id_name} in region {region_name}')
    if not dryrun:
        response = ec2.create_tags(Resources=[id_name], Tags=[{
            'Key': tag_name,
            'Value': tag_value
        }])
        print(f'Response from create_tags: {str(response)}')


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


def has_date_passed(expiry_date, today_date):
    return expiry_date is not None and today_date >= expiry_date
