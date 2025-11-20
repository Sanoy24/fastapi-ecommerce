# FastAPI E-Commerce RESTFul API

A robust and scalable RESTful API built with FastAPI for managing an e-commerce platform. This backend handles product catalogs, user authentication, shopping carts, order processing, and more.

## 🚀 Features

- **User Management**: Secure user registration, login, and profile management using JWT authentication and Argon2 hashing.
- **Product Catalog**: Manage products and categories with support for hierarchical structures.
- **Shopping Cart**: Full-featured shopping cart functionality (add, remove, update items).
- **Order Processing**: comprehensive order lifecycle management from creation to completion.
- **Payments**: Integration ready for payment processing (Data models included).
- **Reviews**: Product review and rating system.
- **Address Management**: Manage user shipping and billing addresses.
- **Database**: SQL-based persistence using SQLAlchemy ORM with Alembic for migrations.
- **Monitoring**: Integrated Sentry for error tracking and performance monitoring.
- **Documentation**: Interactive API documentation via Swagger UI and ReDoc.

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Language**: Python 3.10+
- **Database ORM**: [SQLAlchemy](https://www.sqlalchemy.org/)
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
- **Validation**: [Pydantic](https://docs.pydantic.dev/)
- **Authentication**: PyJWT, Argon2-cffi
- **Server**: Uvicorn
- **Logging**: Loguru

## 📋 Prerequisites

- Python 3.10 or higher
- Git

## 🔧 Installation

1.  **Clone the repository**

    ```bash
    git clone https://github.com/yourusername/fastapi-ecommerce.git
    cd fastapi-ecommerce
    ```

2.  **Create a virtual environment**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Environment Configuration**

    Create a `.env` file in the root directory. You can use the following template:

    ```env
    DATABASE_URL=sqlite:///./ecommerce.db
    SECRET_KEY=your_super_secret_key
    ALGORITHM=HS256
    ACCESS_TOKEN_EXPIRE_MINUTES=30
    # Add other necessary variables
    ```

## 🗄️ Database Setup

Initialize the database and apply migrations:

```bash
# Apply existing migrations
alembic upgrade head
```

## 🚀 Running the Application

Start the development server using Uvicorn:

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000/api/v1`.

## 🐳 Docker Support

You can also run the application using Docker.

1.  **Build the image**

    ```bash
    docker build -t fastapi-ecommerce .
    ```

2.  **Run the container**

    ```bash
    docker run -d -p 8000:8000 fastapi-ecommerce
    ```

## 📚 API Documentation

Once the application is running, you can access the interactive documentation:

- **Swagger UI**: [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)
- **ReDoc**: [http://127.0.0.1:8000/api/v1/redoc](http://127.0.0.1:8000/api/v1/redoc)

## 📂 Project Structure

```
fastapi-ecommerce/
├── alembic/              # Database migrations
├── app/
│   ├── api/              # API route handlers
│   ├── core/             # Core configuration (config, security)
│   ├── crud/             # CRUD operations
│   ├── db/               # Database connection and session
│   ├── middleware/       # Custom middlewares
│   ├── models/           # SQLAlchemy database models
│   ├── schema/           # Pydantic schemas (request/response)
│   ├── services/         # Business logic
│   ├── utils/            # Utility functions
│   └── main.py           # Application entry point
├── tests/                # Test suite
├── .env                  # Environment variables
├── .gitignore
├── alembic.ini           # Alembic configuration
├── docker-compose.yml    # Docker composition (if applicable)
├── Dockerfile
├── requirements.txt      # Python dependencies
└── README.md
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1.  Fork the project
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Contact

Yonas Mekonnen - [Portfolio](https://yonas-mekonnen-portfolio.vercel.app/) - myonas886@gmail.com
