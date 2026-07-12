from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token
)


def test_hash_password():
    password = "password123"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True


def test_wrong_password():
    password = "password123"

    hashed = hash_password(password)

    assert verify_password("wrongpassword", hashed) is False


def test_company_jwt():
    token = create_access_token(
        {
            "type": "company",
            "company_id": 1
        }
    )

    payload = decode_access_token(token)

    assert payload["type"] == "company"
    assert payload["company_id"] == 1


def test_employee_jwt():
    token = create_access_token(
        {
            "type": "employee",
            "employee_id": 5,
            "company_id": 2,
            "role": "manager"
        }
    )

    payload = decode_access_token(token)

    assert payload["type"] == "employee"
    assert payload["employee_id"] == 5
    assert payload["company_id"] == 2
    assert payload["role"] == "manager"