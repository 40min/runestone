from sqlalchemy.exc import IntegrityError


def is_postgresql_unique_violation(exc: IntegrityError, supported_constraints: set[str]) -> bool:
    """Return whether an integrity error names a supported PostgreSQL unique constraint."""
    pending = [exc.orig]
    seen: set[int] = set()
    has_unique_violation_state = False
    constraint_names: set[str] = set()

    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))

        sqlstate = getattr(current, "sqlstate", None) or getattr(current, "pgcode", None)
        has_unique_violation_state = has_unique_violation_state or sqlstate == "23505"

        constraint_name = getattr(current, "constraint_name", None)
        diagnostic = getattr(current, "diag", None)
        if diagnostic is not None:
            constraint_name = constraint_name or getattr(diagnostic, "constraint_name", None)
        if constraint_name:
            constraint_names.add(constraint_name)

        pending.extend((getattr(current, "__cause__", None), getattr(current, "__context__", None)))

    return has_unique_violation_state and bool(constraint_names & supported_constraints)
