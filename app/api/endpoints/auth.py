# import time

# from fastapi import Depends, HTTPException, status
# from sqlalchemy.orm import Session

# from app.core.cardano_auth import generate_nonce, verify_signature
# from app.core.config import settings
# from app.core.router_decorated import APIRouter
# from app.core.jwt_utils import create_access_token
# from app.db.session import get_db
# import app.schemas.auth as schemas
# from app.models.auth import AuthNonce, WalletUser

# router = APIRouter()
# group_tags = ["Auth"]


# @router.post(
#     "/request_nonce",
#     tags=group_tags,
#     response_model=schemas.NonceResponse,
#     status_code=status.HTTP_201_CREATED,
# )
# def request_nonce(body: schemas.NonceRequest, db: Session = Depends(get_db)) -> schemas.NonceResponse:
#     """Generate and store a nonce for a wallet address."""
#     address = body.address.strip()
#     if not address:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Address is required")

#     nonce = generate_nonce()
#     now = int(time.time())
#     expires_at = now + settings.NONCE_EXPIRY_SECONDS

#     existing = db.query(AuthNonce).filter(AuthNonce.address == address).first()
#     if existing:
#         db.delete(existing)

#     db.add(AuthNonce(nonce=nonce, address=address, created_at=now, expires_at=expires_at))
#     db.commit()

#     return schemas.NonceResponse(nonce=nonce)


# @router.post(
#     "/verify",
#     tags=group_tags,
#     response_model=schemas.AuthResponse,
# )
# def verify_wallet(body: schemas.VerifyRequest, db: Session = Depends(get_db)) -> schemas.AuthResponse:
#     """Verify a signed nonce and return an access token."""
#     nonce_record = db.query(AuthNonce).filter(AuthNonce.nonce == body.nonce.strip()).first()
#     if not nonce_record:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nonce not found")

#     if nonce_record.address != body.address.strip():
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Address does not match nonce owner")

#     if nonce_record.expires_at < int(time.time()):
#         db.delete(nonce_record)
#         db.commit()
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nonce expired")

#     is_valid, normalized_address = verify_signature(body.address, body.nonce, body.signature, body.key)
#     if not is_valid:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

#     now = int(time.time())
#     user = db.query(WalletUser).filter(WalletUser.wallet_address == normalized_address).first()
#     if user:
#         user.last_login = now
#     else:
#         db.add(WalletUser(wallet_address=normalized_address, created_at=now, last_login=now))

#     db.delete(nonce_record)
#     db.commit()

#     token = create_access_token(normalized_address)
#     return schemas.AuthResponse(access_token=token, wallet_address=normalized_address)

