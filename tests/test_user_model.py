from app.models.models import User, UserRole, ContractType


def test_user_model_has_contract_type_field():
    user = User(
        organization_id=1,
        email='test@example.com',
        hashed_password='hashed',
        first_name='Test',
        last_name='User',
        role=UserRole.EMPLOYEE,
        contract_type=ContractType.PART_TIME,
    )

    assert hasattr(user, 'contract_type')
    assert user.contract_type == ContractType.PART_TIME
