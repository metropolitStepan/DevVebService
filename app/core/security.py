import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.config import settings


ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class TokenValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class TokenPayload:
    sub: int
    role: str
    token_type: str
    exp: int
    iat: int
    nbf: int
    jti: str


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty")

    password_bytes = password.encode("utf-8")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password_bytes,
        salt,
        settings.password_hash_iterations,
    )

    salt_encoded = _b64url_encode(salt)
    digest_encoded = _b64url_encode(digest)
    return f"pbkdf2_sha256${settings.password_hash_iterations}${salt_encoded}${digest_encoded}"


def validate_password_policy(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")
    if len(password) > 128:
        raise ValueError("Password must contain at most 128 characters")
    if not any(char.isalpha() for char in password):
        raise ValueError("Password must contain at least one letter")
    if not any(char.isdigit() for char in password):
        raise ValueError("Password must contain at least one digit")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_encoded, digest_encoded = password_hash.split("$", maxsplit=3)
        if algorithm != "pbkdf2_sha256":
            return False

        iterations = int(iterations_raw)
        salt = _b64url_decode(salt_encoded)
        expected_digest = _b64url_decode(digest_encoded)
    except (ValueError, TypeError):
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def create_access_token(user_id: int, role: str) -> str:
    return _create_token(
        user_id=user_id,
        role=role,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.access_token_ttl_minutes),
    )


def create_refresh_token(user_id: int, role: str) -> str:
    return _create_token(
        user_id=user_id,
        role=role,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=settings.refresh_token_ttl_days),
    )


def decode_token(token: str, expected_type: str | None = None) -> TokenPayload:
    if not token or len(token.encode("utf-8")) > settings.max_token_bytes:
        raise TokenValidationError("INVALID_TOKEN", "Token is missing or too large")

    encoded_header, encoded_payload, signature = _split_token(token)
    message = f"{encoded_header}.{encoded_payload}"

    expected_signature = _sign(message)
    if not hmac.compare_digest(expected_signature, signature):
        raise TokenValidationError("INVALID_TOKEN_SIGNATURE", "Token signature is invalid")

    header = _decode_json_part(encoded_header, part_name="header")
    payload = _decode_json_part(encoded_payload, part_name="payload")

    if header.get("alg") != settings.jwt_algorithm or header.get("typ") != "JWT":
        raise TokenValidationError("INVALID_TOKEN_HEADER", "Token header is invalid")

    token_type = str(payload.get("type", ""))
    if expected_type is not None and token_type != expected_type:
        raise TokenValidationError("INVALID_TOKEN_TYPE", "Unexpected token type")

    now_ts = int(datetime.now(UTC).timestamp())
    skew = settings.token_clock_skew_seconds

    exp = _parse_int_claim(payload, "exp")
    iat = _parse_int_claim(payload, "iat")
    nbf = _parse_int_claim(payload, "nbf")

    if now_ts > exp + skew:
        raise TokenValidationError("TOKEN_EXPIRED", "Token has expired")
    if now_ts + skew < nbf:
        raise TokenValidationError("TOKEN_NOT_ACTIVE", "Token is not active yet")
    if iat > now_ts + skew:
        raise TokenValidationError("INVALID_TOKEN_IAT", "Token issue time is invalid")

    if payload.get("iss") != settings.jwt_issuer:
        raise TokenValidationError("INVALID_TOKEN_ISSUER", "Token issuer is invalid")
    if payload.get("aud") != settings.jwt_audience:
        raise TokenValidationError("INVALID_TOKEN_AUDIENCE", "Token audience is invalid")

    sub_raw = payload.get("sub")
    if not isinstance(sub_raw, str) or not sub_raw.isdigit():
        raise TokenValidationError("INVALID_TOKEN_SUBJECT", "Token subject is invalid")

    role = payload.get("role")
    if not isinstance(role, str) or not role:
        raise TokenValidationError("INVALID_TOKEN_ROLE", "Token role is invalid")

    jti = payload.get("jti")
    if not isinstance(jti, str) or not jti:
        raise TokenValidationError("INVALID_TOKEN_JTI", "Token identifier is invalid")

    return TokenPayload(
        sub=int(sub_raw),
        role=role,
        token_type=token_type,
        exp=exp,
        iat=iat,
        nbf=nbf,
        jti=jti,
    )


def token_fingerprint(token: str) -> str:
    digest = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        msg=f"refresh:{token}".encode("utf-8"),
        digestmod=hashlib.sha256,
    )
    return digest.hexdigest()


def _split_token(token: str) -> tuple[str, str, str]:
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise TokenValidationError("INVALID_TOKEN", "Token format is invalid")
    return parts[0], parts[1], parts[2]


def _parse_int_claim(payload: dict[str, object], claim_name: str) -> int:
    value = payload.get(claim_name)
    if not isinstance(value, int):
        raise TokenValidationError("INVALID_TOKEN_CLAIM", f"Claim {claim_name} must be an integer")
    return value


def _create_token(user_id: int, role: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    iat = int(now.timestamp())
    exp = int((now + expires_delta).timestamp())

    payload: dict[str, str | int] = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": iat,
        "nbf": iat,
        "exp": exp,
        "jti": str(uuid4()),
    }
    return _encode_token(payload)


def _encode_token(payload: dict[str, str | int]) -> str:
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}

    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    message = f"{encoded_header}.{encoded_payload}"
    signature = _sign(message)
    return f"{message}.{signature}"


def _decode_json_part(value: str, part_name: str) -> dict[str, object]:
    try:
        raw = _b64url_decode(value)
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TokenValidationError("INVALID_TOKEN", f"Token {part_name} is invalid") from error

    if not isinstance(parsed, dict):
        raise TokenValidationError("INVALID_TOKEN", f"Token {part_name} must be an object")
    return parsed


def _sign(message: str) -> str:
    digest = hmac.new(settings.jwt_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
    return _b64url_encode(digest.digest())


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
