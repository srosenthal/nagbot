@dataclass
class Snapshot(Resource):
    state: str
    ec2_type: str
    monthly_price: float
    monthly_server_price: float
    monthly_storage_price: float
    size: float