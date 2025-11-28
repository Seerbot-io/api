from app.schemas.my_base_model import CustormBaseModel


class Statistics(CustormBaseModel):
    """Statistics response model for web content"""
    n_pair: str = ''
    liquidity: str = ''
    n_tx: str = ''

class Partner(CustormBaseModel):
    """Partner response model for web content"""
    name: str = ''
    logo: str = ''
    url: str = ''