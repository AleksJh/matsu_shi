from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.chunk import Chunk  # noqa: E402, F401  # required for Alembic autogenerate
from app.models.document import Document  # noqa: E402, F401  # required for Alembic autogenerate
from app.models.query import Query  # noqa: E402, F401  # required for Alembic autogenerate
from app.models.user import User  # noqa: E402, F401  # required for Alembic autogenerate
from app.models.session import DiagnosticSession  # noqa: E402, F401  # required for Alembic autogenerate
from app.models.admin_user import AdminUser  # noqa: E402, F401  # required for Alembic autogenerate
from app.models.feedback import Feedback  # noqa: E402, F401  # required for Alembic autogenerate
