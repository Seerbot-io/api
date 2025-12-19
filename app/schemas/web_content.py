from app.schemas.my_base_model import CustomBaseModel


class Statistics(CustomBaseModel):
    """Statistics response model for web content"""

    n_pair: str = ""
    liquidity: str = ""
    n_tx: str = ""


class Partner(CustomBaseModel):
    """Partner response model for web content"""

    name: str = ""
    logo: str = ""
    url: str = ""
