import enum


class EmployeeRole(str, enum.Enum):
    employee = "employee"
    manager = "manager"


class InvitationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"


class InvitedByType(str, enum.Enum):
    company = "company"
    employee = "employee"


class OfferedRole(str, enum.Enum):
    manager = "manager"
    employee = "employee"


class OTPPurpose(str, enum.Enum):
    register = "register"
    reset_password = "reset_password"
    change_password = "change_password"