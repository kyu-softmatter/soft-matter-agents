"""Roles, account states and what each role may do.

Roles (docs/PLAN.md 5절): ``admin`` manages users, ``operator`` moves the hardware, ``viewer``
only looks. Each role includes the one below it, so an admin may also operate.

Some actions are **local only**: the request must come from the microscope PC itself
(loopback; the server decides that and passes ``local``). Remote viewing stays read-only, so
hardware commands, submitting a question to the assistant and writing a map flag need both
the role and a local request (D16). Hiding a button in the UI is not the check; the server
routes call ``allows`` / ``control.authorize``.

``STOP`` (``abort``, ``lights_off``) is not a role permission: anyone may send it, with or
without device control and while their login is locked (design rule 12). ``allows`` returns
True for it for every role, and ``control.authorize`` accepts it even with no login at all.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class AccountStatus(StrEnum):
    #: self-registered, waiting for an admin to approve it and set its role; cannot log in
    PENDING = "pending"
    ACTIVE = "active"
    #: switched off by an admin; cannot log in. Accounts are never deleted (the audit log
    #: refers to them)
    DISABLED = "disabled"


class Action(StrEnum):
    VIEW = "view"
    #: anything that moves hardware or changes its state (move, light, objective, scan start)
    OPERATE = "operate"
    #: abort and lights_off
    STOP = "stop"
    MANAGE_USERS = "manage_users"
    #: put a question to the assistant from a prompt box (D16)
    SUBMIT_QUESTION = "submit_question"
    #: add or change a flag on a sample map (D16)
    WRITE_MAP_FLAG = "write_map_flag"


_RANK = {Role.VIEWER: 0, Role.OPERATOR: 1, Role.ADMIN: 2}
_NEEDS = {
    Action.VIEW: Role.VIEWER,
    Action.STOP: Role.VIEWER,
    Action.OPERATE: Role.OPERATOR,
    Action.MANAGE_USERS: Role.ADMIN,
    Action.SUBMIT_QUESTION: Role.OPERATOR,
    Action.WRITE_MAP_FLAG: Role.OPERATOR,
}

#: Actions refused unless the request comes from the microscope PC (loopback)
LOCAL_ONLY = frozenset({Action.OPERATE, Action.SUBMIT_QUESTION, Action.WRITE_MAP_FLAG})

#: Role a new self-registered account carries until an admin approves it (D12)
DEFAULT_ROLE = Role.VIEWER


def allows(role: Role | str, action: Action | str, *, local: bool = False) -> bool:
    """May ``role`` do ``action``? Local-only actions also need ``local=True``."""
    action = Action(action)
    if action in LOCAL_ONLY and local is not True:
        return False
    return _RANK[Role(role)] >= _RANK[_NEEDS[action]]
