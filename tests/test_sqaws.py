import unittest
from unittest.mock import patch

import app.sqaws


class TestAws(unittest.TestCase):
    def test_make_tags_dict(self):
        tags_list = [{'Key': 'Contact', 'Value': 'stephen.rosenthal@seeq.com'},
                     {'Key': 'Stop after', 'Value': '2020-01-01'},
                     {'Key': 'Terminate after', 'Value': '2021-01-01'},
                     {'Key': 'Name', 'Value': 'super-cool-server.seeq.com'}]

        tags_dict = app.sqaws.make_tags_dict(tags_list)

        assert tags_dict == {'Contact': 'stephen.rosenthal@seeq.com',
                             'Stop after': '2020-01-01',
                             'Terminate after': '2021-01-01',
                             'Name': 'super-cool-server.seeq.com'}

    @patch('app.sqaws.boto3.client')
    def test_set_tag(self, mock_client):
        region_name = 'us-east-1'
        instance_id = 'i-0f06b49c1f16dcfde'
        tag_name = 'Stop after'
        tag_value = '2019-12-25'
        mock_ec2 = mock_client.return_value

        app.sqaws.set_tag(region_name, instance_id, tag_name, tag_value, dryrun=False)

        mock_client.assert_called_once_with('ec2', region_name=region_name)
        mock_ec2.create_tags.assert_called_once_with(Resources=[instance_id], Tags=[{
            'Key': tag_name,
            'Value': tag_value
        }])

    @patch('app.sqaws.boto3.client')
    def test_stop_instance(self, mock_client):
        region_name = 'us-east-1'
        instance_id = 'i-0f06b49c1f16dcfde'
        mock_ec2 = mock_client.return_value

        assert app.sqaws.stop_instance(region_name, instance_id, dryrun=False)

        mock_client.assert_called_once_with('ec2', region_name=region_name)
        mock_ec2.stop_instances.assert_called_once_with(InstanceIds=[instance_id])

    @patch('app.sqaws.boto3.client')
    def test_stop_instance_exception(self, mock_client):
        # Note: I haven't seen the call to stop_instance fail, but it certainly could.
        def raise_error():
            raise RuntimeError('An error occurred (OperationNotPermitted)...')

        region_name = 'us-east-1'
        instance_id = 'i-0f06b49c1f16dcfde'
        mock_ec2 = mock_client.return_value
        mock_ec2.stop_instances.side_effect = lambda *args, **kw: raise_error()

        assert not app.sqaws.stop_instance(region_name, instance_id, dryrun=False)

        mock_client.assert_called_once_with('ec2', region_name=region_name)
        mock_ec2.stop_instances.assert_called_once_with(InstanceIds=[instance_id])

    @patch('app.sqaws.boto3.client')
    def test_terminate_instance(self, mock_client):
        region_name = 'us-east-1'
        instance_id = 'i-0f06b49c1f16dcfde'
        mock_ec2 = mock_client.return_value

        assert app.sqaws.terminate_instance(region_name, instance_id, dryrun=False)

        mock_client.assert_called_once_with('ec2', region_name=region_name)
        mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=[instance_id])

    @patch('app.sqaws.boto3.client')
    def test_terminate_instance_exception(self, mock_client):
        # Note: I've seen the call to terminate_instance fail when termination protection is enabled
        def raise_error():
            # The real Boto SDK raises botocore.exceptions.ClientError, but this is close enough
            raise RuntimeError('An error occurred (OperationNotPermitted)...')

        region_name = 'us-east-1'
        instance_id = 'i-0f06b49c1f16dcfde'
        mock_ec2 = mock_client.return_value
        mock_ec2.terminate_instances.side_effect = lambda *args, **kw: raise_error()

        assert not app.sqaws.terminate_instance(region_name, instance_id, dryrun=False)

        mock_client.assert_called_once_with('ec2', region_name=region_name)
        mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=[instance_id])


if __name__ == '__main__':
    unittest.main()
