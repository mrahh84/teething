# Django Common App - Employee Event Tracking

```Name to be confirmed```

## Description

This Django app (`common`) provides models and views for tracking employee events, primarily focusing on clock-in/clock-out status.

It includes a basic web interface for security personnel and a RESTful API for programmatic access.

## Features

* **Models:** Defines data structures for `Card`, `Employee`, `Location`, `EventType`, and `Event`.
* **Clock Status:** The `Employee` model calculates current clock-in/out status based on the latest relevant `Event`.
* **Web Interface (Login Required):**
    * `/common/main_security/`: Displays a list of employees, their current clock-in/out status, and provides buttons to manually clock them in or out. Includes links to individual employee event history.
    * `/common/employee_events/<id>/`: Shows a detailed, timestamped list of events for a specific employee, including event type and location. Provides a link to the Django admin for editing specific events.
* **REST API:**
    * Provides endpoints for listing and managing Events, Employees, and Locations.
    * Read operations (GET) are publicly accessible.
    * Write operations (POST, PUT, PATCH, DELETE) require user authentication.
* **Authentication:** Uses Django's built-in session authentication (`django.contrib.auth`) for both the web interface and API write access.

## Setup

1.  **Prerequisites:** Ensure Django, Django Rest Framework, and DRF Spectacular are installed in your environment.
    ```bash
    pip3 install Django djangorestframework drf-spectacular
    ```
2.  **Migrations:** Apply the app's database migrations if needed:
    ```bash
    python3 manage.py makemigrations common
    python3 manage.py makemigrations
    python3 manage.py migrate
    ```
3.  **Initial Data (Required for Core Functionality):**
    * Create an `EventType` instance with the exact name: `"Clock In"`
    * Create an `EventType` instance with the exact name: `"Clock Out"`
    * Create a `Location` instance with the exact name: `"Main Security"`
    *(This can be done via the Django admin or a data migration).*
4.  **Create Users:** Create user accounts to log into the web interface (e.g., via `python manage.py createsuperuser`).
5.  **Generate API Schema:** Generate the API schema using DRF Spectacular:
    ```bash
    python3 manage.py spectacular --color --validate --color --file schema.yml
    ```

## Running

1.  Start the Django development server:
    ```bash
    docker-compose up
    # python3 manage.py runserver
    ```
2.  Access the web interface by logging in and navigating to `/common/main_security/`.
3.  Access the API endpoints under `/common/api/` and the Swagger UI at `/` i.e. the home page.

## API Endpoints (Brief)

* `GET /common/api/events/` (List, public)
* `GET /common/api/events/<id>/` (Retrieve, public)
* `GET /common/api/employees/<id>/` (Retrieve, public)
* `GET /common/api/locations/<id>/` (Retrieve, public)
* *Authentication required for POST, PUT, PATCH, DELETE on detail endpoints (`.../<id>/`).*
