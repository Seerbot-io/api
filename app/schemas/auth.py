from app.schemas.my_base_model import CustormBaseModel


class NonceRequest(CustormBaseModel):
    address: str


class NonceResponse(CustormBaseModel):
    nonce: str = ""


class VerifyRequest(CustormBaseModel):
    address: str
    nonce: str
    signature: str
    key: str


class AuthResponse(CustormBaseModel):
    access_token: str
    token_type: str = "bearer"
    wallet_address: str

