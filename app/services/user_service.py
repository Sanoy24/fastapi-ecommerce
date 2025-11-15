from app.schema.user_schema import (
    CreateUserSchema,
    UserPublic,
    LoginSchema,
    TokenSchema,
    UpdateUserSchema,
)
from app.models.user import User
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.crud.user import UserCrud
from app.utils.security import verify_password, create_token


class UserService:
    def __init__(self, db: Session):
        """
        Initialize the UserService with a database session.

        This service handles user-related operations such as creation, authentication,
        login, updates, and deletion. It interacts with the UserCrud for database operations.

        Parameters:
        - db (Session): The SQLAlchemy database session for performing queries and commits.
        """
        self.db = db
        self.crud = UserCrud(db=db)

    def create_user(self, user_create_data: CreateUserSchema) -> UserPublic:
        """
        Create a new user based on the provided data.

        This method checks for existing users with the same email, raises an exception if found,
        and then creates the user using the CRUD layer.

        Parameters:
        - user_create_data (CreateUserSchema): The schema containing user creation data like email and password.

        Returns:
        - UserPublic: The public representation of the newly created user.

        Raises:
        - HTTPException: 400 Bad Request if a user with the same email already exists.
        """
        if self.crud.get_user_by_email(user_create_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )
        user = self.crud.create_user(user_create_data=user_create_data)
        return UserPublic.model_validate(user)

    def authenticate_user(self, user_login_data: LoginSchema) -> User:
        """
        Authenticate a user based on login credentials.

        This method retrieves the user by email and verifies the password. If either fails,
        it returns None.

        Parameters:
        - user_login_data (LoginSchema): The schema containing email and password for login.

        Returns:
        - User: The authenticated user object if credentials are valid, otherwise None.
        """
        user = self.crud.get_user_by_email(email=user_login_data.email)
        if not user:
            return None
        if not verify_password(user_login_data.password, user.password_hash):
            return None
        return user

    def login(self, user_login_data: LoginSchema) -> TokenSchema:
        """
        Handle user login and generate an access token.

        This method authenticates the user and, if successful, creates a JWT access token.

        Parameters:
        - user_login_data (LoginSchema): The schema containing email and password for login.

        Returns:
        - TokenSchema: The schema containing the JWT token and token type.

        Raises:
        - HTTPException: 401 Unauthorized if authentication fails.
        """
        user = self.authenticate_user(user_login_data=user_login_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        access_token_payload = {"sub": str(user.id)}
        access_token = create_token(data=access_token_payload)
        return TokenSchema(token=access_token, token_type="Bearer")

    def get_user_by_id(self, id: int) -> User:
        """
        Retrieve a user by their ID.

        This method fetches the user from the database using the CRUD layer.

        Parameters:
        - id (int): The unique identifier of the user.

        Returns:
        - User: The user object if found.

        Raises:
        - HTTPException: 404 Not Found if no user exists with the given ID.
        """
        user = self.crud.get_user(user_id=id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    def update_user(self, id: int, update_user_data: UpdateUserSchema) -> UserPublic:
        """
        Update an existing user's information.

        This method retrieves the user, applies the updates from the provided data,
        commits the changes, and refreshes the user object.

        Parameters:
        - id (int): The unique identifier of the user to update.
        - update_user_data (UpdateUserSchema): The schema containing fields to update.

        Returns:
        - UserPublic: The public representation of the updated user.

        Raises:
        - HTTPException: 404 Not Found if no user exists with the given ID.
        """
        user = self.crud.get_user(user_id=id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        for field, value in update_user_data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return UserPublic.model_validate(
            user
        )  # Note: Added model_validate for consistency with return type

    def delete_user(self, id: int):
        """
        Delete a user by their ID.

        This method retrieves the user and deletes it from the database if found.

        Parameters:
        - id (int): The unique identifier of the user to delete.

        Raises:
        - HTTPException: 404 Not Found if no user exists with the given ID.
        """
        user = self.crud.get_user(user_id=id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        self.db.delete(user)
        self.db.commit()
        return
