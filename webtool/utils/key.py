import base64
import os
import secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey, EllipticCurvePublicKey
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PrivateKey, Ed448PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

AllowedPrivateKeys = RSAPrivateKey | EllipticCurvePrivateKey | Ed25519PrivateKey | Ed448PrivateKey
AllowedPublicKeys = RSAPublicKey | EllipticCurvePublicKey | Ed25519PublicKey | Ed448PublicKey


def _save_key(data: bytes, filename: str, extension: str = ".pem") -> None:
    counter = 1
    while True:
        new_filename = f"{filename}{counter}{extension}"
        if not os.path.exists(new_filename):
            with open(new_filename, "wb") as file:
                file.write(data)
            break
        counter += 1


def _serialize_key(
    private_key: ed25519.Ed25519PrivateKey | ed448.Ed448PrivateKey | rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey,
    password: str | bytes | None,
):
    if isinstance(password, bytes):
        encryption = serialization.BestAvailableEncryption(password)
    elif isinstance(password, str):
        encryption = serialization.BestAvailableEncryption(password.encode("utf-8"))
    else:
        encryption = serialization.NoEncryption()

    private_key = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )

    return private_key


def make_symmetric_key(key_bytes: int = 32, save: bool = False) -> bytes:
    key = base64.urlsafe_b64encode(secrets.token_bytes(key_bytes))

    if save:
        _save_key(key, "symmetric_key")

    return key


def make_rsa_key(key_size: int = 2048, save: bool = False, password: str | bytes | None = None) -> bytes:
    if key_size < 2048:
        raise ValueError("Key size must be greater than or equal to 2048")

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )

    private_key = _serialize_key(private_key, password=password)

    if save:
        _save_key(private_key, "rsa_private_key")

    return private_key


def make_ec_key(algorithm: str = "ES256", save: bool = False, password: str | bytes | None = None) -> bytes:
    algorithm = algorithm.upper()

    if algorithm == "ES256":
        private_key = ec.generate_private_key(ec.SECP256R1())
    elif algorithm == "ES256K":
        private_key = ec.generate_private_key(ec.SECP256K1())
    elif algorithm == "ES384":
        private_key = ec.generate_private_key(ec.SECP384R1())
    elif algorithm == "ES512":
        private_key = ec.generate_private_key(ec.SECP521R1())
    else:
        raise ValueError("Algorithm must be ES256, ES256K, ES384, ES512")

    private_key = _serialize_key(private_key, password=password)

    if save:
        _save_key(private_key, "ec_private_key")

    return private_key


def make_ed_key(algorithm: str = "ed25519", save: bool = False, password: str | bytes | None = None) -> bytes:
    algorithm = algorithm.upper()

    if algorithm == "ED25519":
        private_key = ed25519.Ed25519PrivateKey.generate()
    elif algorithm == "ED448":
        private_key = ed448.Ed448PrivateKey.generate()
    else:
        raise ValueError("Curve must be Ed25519 or Ed448")

    private_key = _serialize_key(private_key, password=password)

    if save:
        _save_key(private_key, "ed_private_key")

    return private_key


def load_asymmetric_key(
    private_key: bytes,
    password: str | bytes | None = None,
) -> tuple[AllowedPrivateKeys, AllowedPublicKeys, str] | None:
    if isinstance(password, str):
        password = password.encode("utf-8")

    try:
        private_key = load_pem_private_key(private_key, password=password)
    except ValueError:
        return None

    public_key = private_key.public_key()

    if isinstance(private_key, rsa.RSAPrivateKey):
        key_size = private_key.key_size
        if key_size < 3072:
            algorithm = "RS256"
        elif key_size < 4096:
            algorithm = "RS384"
        else:
            algorithm = "RS512"
    elif isinstance(private_key, ec.EllipticCurvePrivateKey):
        curve = private_key.curve.name
        if curve == "secp256r1":
            algorithm = "ES256"
        elif curve == "secp256k1":
            algorithm = "ES256K"
        elif curve == "secp384r1":
            algorithm = "ES384"
        elif curve == "secp521r1":
            algorithm = "ES512"
        else:
            raise ValueError(
                f"Unsupported elliptic curve: {curve}. "
                "Supported curves are secp256r1, secp256k1, secp384r1, and secp521r1."
            )
    elif isinstance(private_key, (ed25519.Ed25519PrivateKey, ed448.Ed448PrivateKey)):
        algorithm = "EdDSA"
    else:
        raise ValueError(
            f"Unsupported key type: {type(private_key).__name__}. "
            "Supported key types are RSAPrivateKey, EllipticCurvePrivateKey, Ed25519PrivateKey, and Ed448PrivateKey."
        )

    return private_key, public_key, algorithm


def load_key(
    key: bytes | str,
    password: str | bytes | None = None,
) -> tuple[AllowedPrivateKeys, AllowedPublicKeys, str] | tuple[bytes | str, str] | None:
    if isinstance(key, bytes):
        key_cart = load_asymmetric_key(key, password)

        if key_cart:
            return key_cart

    key_size = len(key)

    if key_size < 48:
        key, algorithm = key, "HS256"
    elif key_size < 64:
        key, algorithm = key, "HS384"
    else:
        key, algorithm = key, "HS512"

    return key, algorithm
