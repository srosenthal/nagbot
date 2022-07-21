import json
import traceback

import boto3

HOURS_IN_A_MONTH = 730


class PricingData:
    def __init__(self):
        self.client = boto3.client('pricing', region_name='us-east-1')
        self.cache = {}

    def lookup_monthly_price(self, region_name: str, instance_type: str, operating_system: str) -> float:
        try:
            # Use the AWS API to estimate the monthly price of an instance, assuming used all month, as hourly,
            # on-demand, with no special software (like SQL), and no reservations
            cache_key = (region_name, instance_type, operating_system)
            if cache_key not in self.cache:
                # See https://www.sentiatechblog.com/using-the-ec2-price-list-api for why this is so complicated
                price_json = self.client.get_products(
                    ServiceCode='AmazonEC2',
                    FormatVersion='aws_v1',
                    Filters=[{
                        "Type": "TERM_MATCH",
                        "Field": "ServiceCode",
                        "Value": "AmazonEC2"
                    }, {
                        "Type": "TERM_MATCH",
                        "Field": "licenseModel",
                        "Value": "No License required"
                    }, {
                        "Type": "TERM_MATCH",
                        "Field": "preInstalledSw",
                        "Value": "NA"
                    }, {
                        "Type": "TERM_MATCH",
                        "Field": "capacitystatus",
                        "Value": "Used"
                    }, {
                        "Type": "TERM_MATCH",
                        "Field": "tenancy",
                        "Value": "Shared"
                    }, {
                        "Type": "TERM_MATCH",
                        "Field": "regionCode",
                        "Value": region_name
                    }, {
                        "Type": "TERM_MATCH",
                        "Field": "instanceType",
                        "Value": instance_type
                    }, {
                        "Type": "TERM_MATCH",
                        "Field": "operatingSystem",
                        "Value": operating_system
                    }],
                    MaxResults=1
                )['PriceList'][0]
                price_info = json.loads(price_json)
                on_demand_term = next(iter(price_info['terms']['OnDemand'].values()))
                hourly = float(next(iter(on_demand_term['priceDimensions'].values()))['pricePerUnit']['USD'])
                print(f'{operating_system} on {instance_type} in {region_name} costs ${hourly:.2f}/hr', flush=True)

                self.cache[cache_key] = hourly * HOURS_IN_A_MONTH
            return self.cache[cache_key]
        except:
            print(f'> lookup_monthly_price("{region_name}", "{instance_type}", "{operating_system}")')
            traceback.print_exc()
            raise
