from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all ORM models.

    All database models in the application should inherit from this class.
    It provides SQLAlchemy's declarative mapping functionality.

    Example:
    ```
    class User(Base):
        __tablename__ = "users"
        id = Column(Integer, primary_key=True)
    ```
    """

    pass
