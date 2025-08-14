# Django Common App - Employee Event Tracking

```Name to be confirmed```

## Description

This Django app (`common`) provides models and views for tracking employee events, primarily focusing on clock-in/clock-out status.

It includes a basic web interface for security personnel and a RESTful API for programmatic access.

## Features

* **Models:** Defines data structures for `Card`, `Employee`, `Location`, `EventType`, and `Event`.
* **Clock Status:** The `Employee` model calculates current clock-in/out status based on the latest relevant `Event`.
* **Web Interface (Login Required):**
    * `/common/`: Displays a list of employees, their current clock-in/out status, and provides buttons to manually clock them in or out. Includes links to individual employee event history.
    * `/common/employee_events/<id>/`: Shows a detailed, timestamped list of events for a specific employee, including event type and location. Provides a link to the Django admin for editing specific events.
* **REST API:**
    * Provides endpoints for listing and managing Events, Employees, and Locations.
    * Read operations (GET) are publicly accessible.
    * Write operations (POST, PUT, PATCH, DELETE) require user authentication.
* **Authentication:** Uses Django's built-in session authentication (`django.contrib.auth`) for both the web interface and API write access.

## Setup

1.  **Prerequisites:** Ensure Django, Django Rest Framework, DRF Spectacular, and Python-decouple are installed in your environment.
    ```bash
    pip3 install -r requirements.txt
    ```

2.  **Environment Configuration:**
    * Create a `.env` file in the project root with the following variables:
      ```
      # Django secret key
      SECRET_KEY=your-generated-secret-key
      
      # Debug settings
      DEBUG=True  # Set to False in production
      
      # Allowed hosts (comma separated)
      ALLOWED_HOSTS=localhost,127.0.0.1
      
      # Optional database settings
      # DB_ENGINE=django.db.backends.postgresql
      # DB_NAME=attendance_db
      # DB_USER=postgres
      # DB_PASSWORD=your-secure-password
      # DB_HOST=localhost
      # DB_PORT=5432
      ```
    * Generate a secure secret key:
      ```bash
      python scripts/generate_secret_key.py
      ```

3.  **Migrations:** Apply the app's database migrations if needed:
    ```bash
    python3 manage.py makemigrations common
    python3 manage.py makemigrations
    python3 manage.py migrate
    ```
    
4.  **Initial Data (Required for Core Functionality):**
    * Create an `EventType` instance with the exact name: `"Clock In"`
    * Create an `EventType` instance with the exact name: `"Clock Out"`
    * Create a `Location` instance with the exact name: `"Main Security"`
    *(This can be done via the Django admin or a data migration).*
    
5.  **Create Users:** Create user accounts to log into the web interface (e.g., via `python manage.py createsuperuser`).

6.  **Generate API Schema:** Generate the API schema using DRF Spectacular:
    ```bash
    python3 manage.py spectacular --color --validate --color --file schema.yml
    ```

## Running

1.  Start the Django development server:
    ```bash
    docker-compose up
    # python3 manage.py runserver
    ```
2.  Access the web interface by logging in and navigating to `/common/`.
3.  Access the API endpoints under `/common/api/` and the Swagger UI at `/` i.e. the home page.

## Production Deployment

When deploying to production, make sure to:

1. Generate a new secure secret key using `python scripts/generate_secret_key.py`
2. Set `DEBUG=False` in your `.env` file
3. Specify your domain(s) in `ALLOWED_HOSTS`
4. Use a production-grade database like PostgreSQL
5. Set up proper HTTPS with a valid SSL certificate

## API Endpoints (Brief)

* `GET /common/api/events/` (List, public)
* `GET /common/api/events/<id>/` (Retrieve, public)
* `GET /common/api/employees/<id>/` (Retrieve, public)
* `GET /common/api/locations/<id>/` (Retrieve, public)
* *Authentication required for POST, PUT, PATCH, DELETE on detail endpoints (`.../<id>/`).*
