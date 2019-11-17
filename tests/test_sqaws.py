import sys
import unittest
from unittest.mock import patch

import app.sqaws


class TestAws(unittest.TestCase):
    @patch('app.sqaws.boto3.client')
    def test_stop_instance(self, mock_client):
        region = 'us-east-1'
        instance_id = 'i-0f06b49c1f16dcfde'
        mock_ec2 = mock_client.return_value

        assert app.sqaws.stop_instance(region, instance_id)

        mock_client.assert_called_once_with('ec2', region_name=region)
        mock_ec2.stop_instances.assert_called_once_with(InstanceIds=[instance_id])


    @patch('app.sqaws.boto3.client')
    def test_stop_instance_exception(self, mock_client):
        # Note: I haven't seen the call to stop_instance fail, but it certainly could.
        def raise_error():
            raise RuntimeError('An error occurred (OperationNotPermitted)...')

        region = 'us-east-1'
        instance_id = 'i-0f06b49c1f16dcfde'
        mock_ec2 = mock_client.return_value
        mock_ec2.stop_instances.side_effect = lambda *args, **kw: raise_error()

        assert not app.sqaws.stop_instance(region, instance_id)

        mock_client.assert_called_once_with('ec2', region_name=region)
        mock_ec2.stop_instances.assert_called_once_with(InstanceIds=[instance_id])


    @patch('app.sqaws.boto3.client')
    def test_terminate_instance(self, mock_client):
        region = 'us-east-1'
        instance_id = 'i-0f06b49c1f16dcfde'
        mock_ec2 = mock_client.return_value

        assert app.sqaws.terminate_instance(region, instance_id)

        mock_client.assert_called_once_with('ec2', region_name=region)
        mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=[instance_id])


    @patch('app.sqaws.boto3.client')
    def test_terminate_instance_exception(self, mock_client):
        # Note: I've seen the call to terminate_instance fail when termination protection is enabled
        def raise_error():
            # The real Boto SDK raises botocore.exceptions.ClientError, but this is close enough
            raise RuntimeError('An error occurred (OperationNotPermitted)...')

        region = 'us-east-1'
        instance_id = 'i-0f06b49c1f16dcfde'
        mock_ec2 = mock_client.return_value
        mock_ec2.terminate_instances.side_effect = lambda *args, **kw: raise_error()

        assert not app.sqaws.terminate_instance(region, instance_id)

        mock_client.assert_called_once_with('ec2', region_name=region)
        mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=[instance_id])


if __name__ == '__main__':
    unittest.main()