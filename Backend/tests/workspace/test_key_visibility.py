from app.routers.workspace import company_keys


class FakeQuery:
    def __init__(self):
        self.filters = []

    def filter(self, *criteria):
        self.filters.append(criteria)
        return self

    def order_by(self, *criteria):
        return self


class FakeDB:
    def __init__(self):
        self.query_result = FakeQuery()

    def query(self, model):
        return self.query_result


def test_employee_key_query_is_restricted_to_recipient():
    db = FakeDB()
    company_keys(db, ("employee", 42, 7))
    assert len(db.query_result.filters) == 2


def test_company_admin_cannot_use_member_keys_in_chat():
    db = FakeDB()
    company_keys(db, ("company", 7, 7))
    assert len(db.query_result.filters) == 2
