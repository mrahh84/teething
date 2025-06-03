import marimo

__generated_with = "0.13.15"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    # Django Data Explorer

    This notebook provides powerful tools for exploring Django models, relationships, and data.
    It allows you to quickly understand your Django project structure and analyze data without leaving the Python environment.

    Key features:

    - Automatically configure Django in Marimo with reduced logging noise
    - Explore all available models and their relationships
    - Analyze model relationships in detail (`ForeignKey`, `ManyToMany`, `reverse relations`)
    - Convert Django QuerySets to Polars DataFrames for advanced analysis
    - Measure query performance with detailed diagnostics
    """
    )
    return


@app.cell
def _():
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ## Getting Started

    This notebook connects to your Django project and provides tools to explore its data structure and run queries.

    The functions in this notebook help you:

    1. Understand your Django model structure
    2. Analyze relationships between models
    3. Convert QuerySets to Polars DataFrames for data analysis
    4. Monitor query performance

    To use this notebook, you'll need to specify the path to your Django project in the `setup_django_for_marimo` function below.
    """
    )
    return


@app.cell
def _():
    MAIN_APP_NAME = "attendance"
    PATH = "/Users/D.Clarke/Code/road_attendance_all/develop/"
    return MAIN_APP_NAME, PATH


@app.cell(hide_code=True)
def _(MAIN_APP_NAME, PATH):
    # Non Django Libraires Setup
    import functools
    import logging
    import time
    from collections import Counter
    from typing import Any, Dict, List, Optional, Type, Union

    import marimo as mo
    import polars as pl


    def setup_django_for_marimo(
        main_project_path=None, main_app=MAIN_APP_NAME, set_async_unsafe=True
    ):
        """
        Set up the django environment for working with the Marimo notebook.

        Parameters:
        -----------
        - main_project_path: Path to the Django project root
            Example: "/Users/username/projects/mydjango_project/"
            If None, uses current working directory

        - main_app: Name of the main Django application
            This should be the package containing your settings.py file

        - set_async_unsafe: Whether to allow async unsafe operations
            Set to True to enable database queries in async environments like notebooks

        This function:
        1. Adds the project path to sys.path
        2. Sets DJANGO_SETTINGS_MODULE environment variable
        3. Calls django.setup() to initialize Django
        4. Configures logging to reduce unnecessary debug messages

        Returns:
        --------
        Django settings module

        Example Usage:
        --------------
        ```python
        # Set up Django with path to your project
        setup_django_for_marimo("/path/to/your/django/project/")

        # Now you can import Django models
        from myapp.models import MyModel
        ```

        Based on:
        ---------
            - https://docs.djangoproject.com/en/5.2/topics/settings/
            - https://forum.djangoproject.com/t/anyone-had-look-at-using-marimo-with-django/27182
        """
        import logging
        import os
        import pathlib
        import sys

        import django

        # Setup project path
        if not main_project_path:
            path_obj = pathlib.Path()
            main_project_path = str(path_obj.cwd())

        # Allow async unsafe operations if requested
        if set_async_unsafe:
            os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "True"

        # Add project path to sys.path if not already there
        if main_project_path not in sys.path:
            sys.path.append(main_project_path)

        # Set Django settings module
        os.environ["DJANGO_SETTINGS_MODULE"] = f"{main_app}.settings"
        os.environ["PYTHONPATH"] = main_project_path

        # Disable Django's default logging configuration
        # Initialize Django
        django.setup()

        # Disable the SQL query logging - this is a common source of noise
        logging.getLogger("django.db.backends").setLevel(logging.ERROR)

        # Raise the level for the django root logger to reduce noise
        logging.getLogger("django").setLevel(logging.WARNING)

        # Configure the root logger to suppress most messages
        # Needed in marimo
        logging.getLogger().setLevel(logging.WARNING)

        # After Django is set up, we can further control the logging
        from django.conf import settings

        # Turn off DEBUG in settings if it's set to True
        # This helps reduce the verbosity of logging without changing your project settings
        if settings.configured and settings.DEBUG:
            # Safely modify DEBUG setting after configuration
            settings.__dict__["_wrapped"].__dict__["DEBUG"] = False

        print(f"✅ Django setup complete - Connected to: {main_app}")
        return settings


    # Django Libraries Setup
    # Change this path to your Django project path
    setup_django_for_marimo(PATH)
    from django.apps import apps
    from django.core.exceptions import FieldDoesNotExist
    from django.db import connection, models, reset_queries
    from django.db.models.query import QuerySet
    return (
        Any,
        Counter,
        Dict,
        FieldDoesNotExist,
        Optional,
        QuerySet,
        Type,
        Union,
        apps,
        connection,
        functools,
        logging,
        mo,
        models,
        pl,
        reset_queries,
        time,
    )


@app.cell
def _():
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ## Django Model Explorer

    The section below shows all available models from your Django project, grouped by app. This gives you a quick overview of your project's data structure.

    For each model, you'll see:

    - All fields and their types
    - Related models (if any)

    This is useful for understanding the schema of your Django project before diving into data analysis.
    """
    )
    return


@app.cell(hide_code=True)
def _(apps, mo):
    with mo.redirect_stdout():
        # List all available models
        models_list = apps.get_models()

        # Group models by app
        models_by_app = {}
        for model in models_list:
            app_label = model._meta.app_label
            if app_label not in models_by_app:
                models_by_app[app_label] = []
            models_by_app[app_label].append(model)

        # Display models grouped by app
        for app_label, app_models in models_by_app.items():
            print(f"\n=== {app_label.upper()} APP ===")

            for model in app_models:
                print(f"\n{model.__name__} Fields:")
                for field in model._meta.fields:
                    print(f"\t\t- {field.name}: {field.__class__.__name__}")

                # Show relationships
                if model._meta.related_objects:
                    print(f"\n  Related Models:")
                    for related in model._meta.related_objects:
                        print(
                            f"\t\t- {related.name} ({related.related_model.__name__})"
                        )
                print("----\t----\t----\t----\t----\t----\t----")
            print("====\t====\t====\t====\t====\t====\t====")
    return


@app.cell
def _():
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ## Analysis Tools

    The following functions help you analyze and interact with your Django models. Each tool is designed to solve common challenges when working with Django data.

    ### Three Key Tools:

    1. **analyze_relationships**

       - Understand connections between models
       - Works with ForeignKey, ManyToMany, and reverse relationships
       - Shows distribution, cardinality, and coverage statistics

    2. **queryset_to_pl**

       - Convert Django QuerySets to Polars DataFrames
       - Enables powerful data analysis with Polars
       - Optimized for performance with large datasets

    3. **query_performance**

       - Measure and optimize database queries
       - Tracks query count, time, and SQL statements
       - Identifies slow queries that need optimization

    These tools help bridge the gap between Django's ORM and data analysis, making it easier to understand and work with your project's data.
    """
    )
    return


@app.cell
def _():
    return


@app.cell(hide_code=True)
def _(connection, functools, logging, reset_queries, time):
    def query_performance(
        threshold_ms=None, show_queries=False, log_level="WARNING"
    ):
        """
        Decorator to measure Django query performance with enhanced features.

        This decorator helps you identify and optimize database queries by providing
        detailed statistics about query execution. Use it to wrap any function that
        performs database operations to see how many queries it runs and how long they take.

        Parameters:
        -----------
        threshold_ms : int, optional
            Only highlight queries that take longer than this many milliseconds.
            Example: threshold_ms=100 will flag queries taking more than 100ms

        show_queries : bool, default=False
            Whether to show the actual SQL for each query.
            Set to True when you need to see the exact queries being executed

        log_level : str, default='WARNING'
            Log level to use ('INFO', 'DEBUG', 'WARNING').
            Controls the visibility of the output in the notebook

        Returns:
        --------
        The decorated function with query performance metrics printed

        Example Usage:
        --------------
        ```python
        @query_performance(threshold_ms=50, show_queries=True)
        def get_active_users():
            return User.objects.filter(is_active=True)

        # Call the function and get performance metrics
        users = get_active_users()
        ```

        Tips:
        -----
        - Use show_queries=True to see the exact SQL being executed
        - Look for N+1 query problems (many similar queries)
        - High query counts might indicate missing select_related/prefetch_related
        """

        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Configure logging
                logger = logging.getLogger(f"{func.__module__}.{func.__name__}")
                log_method = getattr(logger, log_level.lower())

                # Need to ensure DEBUG is True for query recording
                from django.conf import settings

                if not settings.DEBUG:
                    log_method(
                        "WARNING: Django DEBUG is False. Query analysis is not available."
                    )
                    return func(*args, **kwargs)

                # Clear the query log
                reset_queries()

                # Time the function execution
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    successful = True
                except Exception as e:
                    successful = False
                    raise e
                finally:
                    end = time.time()
                    duration = end - start

                    # Analyze queries
                    queries = connection.queries
                    query_count = len(queries)

                    # Calculate stats
                    if query_count > 0:
                        query_times = [float(q["time"]) for q in queries]
                        slowest_time = max(query_times) if query_times else 0
                        fastest_time = min(query_times) if query_times else 0
                        avg_time = (
                            sum(query_times) / len(query_times)
                            if query_times
                            else 0
                        )
                        total_query_time = sum(query_times)

                        # Format main output
                        status = "COMPLETED" if successful else "FAILED"
                        summary = (
                            f"Function: {func.__name__} ({status})\n"
                            f"Total time: {duration:.4f}s | Query time: {total_query_time:.4f}s | Non-query time: {duration - total_query_time:.4f}s\n"
                            f"Queries: {query_count} | Avg: {avg_time * 1000:.2f}ms | Min: {fastest_time * 1000:.2f}ms | Max: {slowest_time * 1000:.2f}ms"
                        )
                        log_method(summary)

                        # Optionally show individual queries
                        if show_queries:
                            log_method("Query details:")
                            for i, query in enumerate(queries, 1):
                                query_time = float(query["time"])

                                # Highlight slow queries
                                if (
                                    threshold_ms
                                    and query_time * 1000 > threshold_ms
                                ):
                                    marker = "!!! SLOW QUERY !!!"
                                else:
                                    marker = ""

                                log_method(
                                    f"  [{i}] {query_time * 1000:.2f}ms {marker}\n    {query['sql']}"
                                )
                    else:
                        log_method(
                            f"Function: {func.__name__} - No queries executed. Time: {duration:.4f}s"
                        )

                return result

            return wrapper

        # Support both @query_performance and @query_performance()
        if callable(threshold_ms):
            func = threshold_ms
            threshold_ms = None
            return decorator(func)

        return decorator
    return (query_performance,)


@app.cell(hide_code=True)
def _(Any, Counter, Dict, FieldDoesNotExist, Type, models):
    def analyze_relationships(
        model: Type[models.Model], field_name: str, limit: int = 10
    ) -> Dict[str, Any]:
        """
        Thoroughly analyze a relationship in a Django model.

        This function provides comprehensive statistics about model relationships,
        helping you understand how your data is connected. It automatically detects
        the relationship type and provides relevant metrics.

        Supports:
        ---------
        - ForeignKey fields
        - ManyToManyField fields
        - Reverse relations (related_name)

        Parameters:
        -----------
        model : Type[models.Model]
            The Django model class containing the relationship
            Example: User, Product, Order

        field_name : str
            Name of the relationship field to analyze
            Example: 'orders' (a reverse relation on User), 'category' (ForeignKey on Product)

        limit : int, default=10
            Number of top items to include in distribution results

        Returns:
        --------
        Dict[str, Any]
            Dictionary containing relationship analysis data:
            - distribution: Top records by relation count
            - Coverage metrics (% of records with relations)
            - Cardinality statistics (min/avg/max relations per record)
            - For each relationship type, specialized statistics

        Example Usage:
        --------------
        ```python
        # Analyze orders made by users (reverse relation)
        from django.contrib.auth.models import User
        from orders.models import Order

        results = analyze_relationships(User, 'order_set')

        # Analyze product categories (foreign key)
        from products.models import Product
        results = analyze_relationships(Product, 'category')
        ```

        Tips:
        -----
        - Use this to identify data integrity issues (orphaned records)
        - Find imbalanced relationships that might cause performance problems
        - Understand data distribution across relationships
        """
        # Validate inputs
        if not hasattr(model, "_meta"):
            raise ValueError(
                f"Input '{model}' doesn't appear to be a Django model"
            )

        # First try to get the field directly
        try:
            # Check if this is a direct field
            field = model._meta.get_field(field_name)

            # Different handling based on field type
            if field.is_relation:
                if field.many_to_one:  # ForeignKey
                    relation_type = "ForeignKey"
                    related_model = field.related_model
                    is_m2m = False
                    is_reverse = False
                elif field.many_to_many:  # ManyToManyField
                    relation_type = "ManyToManyField"
                    related_model = field.related_model
                    is_m2m = True
                    is_reverse = False
                else:
                    relation_type = "Unknown relation"
                    related_model = field.related_model
                    is_m2m = False
                    is_reverse = False
            else:
                raise ValueError(f"Field '{field_name}' is not a relation field")

        except FieldDoesNotExist:
            # Check if this is a reverse relation (e.g., related_name)
            reverse_relations = [
                rel
                for rel in model._meta.get_fields()
                if (rel.one_to_many or rel.many_to_many)
                and rel.auto_created
                and rel.name == field_name
            ]

            if reverse_relations:
                rel = reverse_relations[0]
                related_model = rel.model
                if rel.many_to_many:
                    relation_type = "Reverse ManyToManyField"
                    is_m2m = True
                else:
                    relation_type = "Reverse ForeignKey"
                    is_m2m = False
                is_reverse = True
            else:
                raise ValueError(
                    f"Field '{field_name}' not found in model {model.__name__}"
                )

        # Get more descriptive names for reporting
        model_name = model.__name__
        related_model_name = related_model.__name__

        print(
            f"Analyzing relationship: {model_name}.{field_name} → {related_model_name} ({relation_type})"
        )

        # Analysis depends on relationship type
        if is_m2m:
            return analyze_m2m_relationship(
                model, related_model, field_name, is_reverse, limit
            )
        elif is_reverse:
            return analyze_reverse_fk_relationship(
                model, related_model, field_name, limit
            )
        else:
            return analyze_fk_relationship(model, related_model, field_name, limit)


    def analyze_fk_relationship(
        model: Type[models.Model],
        related_model: Type[models.Model],
        fk_field: str,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Analyze a regular ForeignKey relationship."""
        model_name = model.__name__
        related_model_name = related_model.__name__

        # Distribution of records by foreign key
        distribution = (
            model.objects.values(
                f"{fk_field}__id",
                f"{fk_field}__pk",
                # Try to get a descriptive field from the related model
                *(
                    f"{fk_field}__{field.name}"
                    for field in related_model._meta.fields
                    if field.name in ("name", "title", "description", "label")
                ),
            )
            .annotate(count=models.Count("id"))
            .order_by("-count")
        )

        # Records with null foreign keys
        null_fks = model.objects.filter(**{f"{fk_field}__isnull": True}).count()

        # Foreign keys without related records (orphaned references)
        all_related_ids = set(related_model.objects.values_list("id", flat=True))
        referenced_ids = set(
            model.objects.exclude(**{f"{fk_field}__isnull": True})
            .values_list(f"{fk_field}", flat=True)
            .distinct()
        )

        orphaned_fks = related_model.objects.filter(
            ~models.Q(id__in=model.objects.values_list(fk_field, flat=True))
        ).count()

        # Calculate cardinality statistics
        cardinality_stats = (
            model.objects.exclude(**{f"{fk_field}__isnull": True})
            .values(fk_field)
            .annotate(count=models.Count("id"))
            .aggregate(
                avg=models.Avg("count"),
                min=models.Min("count"),
                max=models.Max("count"),
            )
        )

        # Calculate coverage percentage
        total_related = related_model.objects.count()
        coverage_percentage = (
            (len(referenced_ids) / total_related * 100) if total_related > 0 else 0
        )

        # Format distribution for display
        formatted_distribution = []
        for item in distribution[:limit]:
            entry = {"count": item["count"]}

            # Try to find a readable identifier
            identifier = None
            for key, value in item.items():
                if (
                    key not in ("count", f"{fk_field}__id", f"{fk_field}__pk")
                    and value
                ):
                    identifier = value
                    break

            # Fall back to ID if no readable identifier found
            if identifier:
                entry["identifier"] = identifier
            else:
                entry["id"] = item.get(f"{fk_field}__id") or item.get(
                    f"{fk_field}__pk"
                )

            formatted_distribution.append(entry)

        # Print the results in a readable format
        print("\n=== RELATIONSHIP ANALYSIS RESULTS ===")
        print(f"Null Foreign Keys: {null_fks}")
        print(f"Orphaned Foreign Keys: {orphaned_fks}")
        print(
            f"Coverage: {coverage_percentage:.1f}% ({len(referenced_ids)}/{total_related})"
        )

        print("\nCardinality:")
        try:
            print(
                f"  Average: {cardinality_stats['avg']:.2f} records per foreign key"
            )
        except:
            print(f"  Average: unknown records per foreign key")
        try:
            print(f"  Min: {cardinality_stats['min']} records")
        except:
            print(f"  Min: unknown records")
        try:
            print(f"  Max: {cardinality_stats['max']} records")
        except:
            print(f"  Max: unknown records")

        print(f"\nTop {limit} Distribution:")
        for i, item in enumerate(formatted_distribution, 1):
            if "identifier" in item:
                print(f"  {i}. {item['identifier']}: {item['count']} records")
            else:
                print(f"  {i}. ID {item['id']}: {item['count']} records")

        # Distribution histogram as text
        if distribution.exists():
            all_counts = list(
                model.objects.values(fk_field)
                .annotate(count=models.Count("id"))
                .values_list("count", flat=True)
            )

            if all_counts:
                count_counter = Counter(all_counts)
                max_count = max(all_counts)
                bucket_size = max(1, max_count // 10)  # Create roughly 10 buckets

                print("\nDistribution Histogram:")
                print("  Records | Frequency")
                print("  ------------------------------")

                # Create bucketed histogram
                buckets = {}
                for i in range(0, max_count + bucket_size, bucket_size):
                    bucket_min = i
                    bucket_max = i + bucket_size - 1
                    bucket_label = f"{bucket_min}-{bucket_max}"

                    bucket_count = sum(
                        count_counter[j]
                        for j in range(bucket_min, bucket_max + 1)
                        if j in count_counter
                    )

                    if bucket_count > 0:
                        buckets[bucket_label] = bucket_count

                # Print as text histogram
                for label, count in buckets.items():
                    bar = "█" * min(40, count)  # Limit bar length to 40 chars
                    print(f"  {label:7} | {count:4} {bar}")

        return {
            "distribution": formatted_distribution,
            "null_fks": null_fks,
            "orphaned_fks": orphaned_fks,
            "cardinality": cardinality_stats,
            "coverage": {
                "referenced_count": len(referenced_ids),
                "total_count": total_related,
                "percentage": coverage_percentage,
            },
        }


    def analyze_reverse_fk_relationship(
        model: Type[models.Model],
        related_model: Type[models.Model],
        relation_name: str,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Analyze a reverse ForeignKey relationship."""
        model_name = model.__name__
        related_model_name = related_model.__name__

        # In a reverse FK relationship, the related model has the FK field pointing to the main model

        # Distribution of records by main model
        distribution = (
            related_model.objects.values(
                f"{relation_name}__id",
                f"{relation_name}__pk",
                # Try to get a descriptive field from the main model
                *(
                    f"{relation_name}__{field.name}"
                    for field in model._meta.fields
                    if field.name in ("name", "title", "description", "label")
                ),
            )
            .annotate(count=models.Count("id"))
            .order_by("-count")
        )

        # Main models without related records
        models_without_related = model.objects.filter(
            ~models.Q(
                id__in=related_model.objects.values_list(relation_name, flat=True)
            )
        ).count()

        # Calculate cardinality statistics
        cardinality_stats = (
            related_model.objects.values(relation_name)
            .annotate(count=models.Count("id"))
            .aggregate(
                avg=models.Avg("count"),
                min=models.Min("count"),
                max=models.Max("count"),
            )
        )

        # Calculate coverage percentage
        total_main = model.objects.count()
        referenced_main_ids = set(
            related_model.objects.values_list(relation_name, flat=True).distinct()
        )
        coverage_percentage = (
            (len(referenced_main_ids) / total_main * 100) if total_main > 0 else 0
        )

        # Format distribution for display
        formatted_distribution = []
        for item in distribution[:limit]:
            entry = {"count": item["count"]}

            # Try to find a readable identifier
            identifier = None
            for key, value in item.items():
                if (
                    key
                    not in (
                        "count",
                        f"{relation_name}__id",
                        f"{relation_name}__pk",
                    )
                    and value
                ):
                    identifier = value
                    break

            # Fall back to ID if no readable identifier found
            if identifier:
                entry["identifier"] = identifier
            else:
                entry["id"] = item.get(f"{relation_name}__id") or item.get(
                    f"{relation_name}__pk"
                )

            formatted_distribution.append(entry)

        # Print the results in a readable format
        print("\n=== REVERSE RELATIONSHIP ANALYSIS RESULTS ===")
        print(f"Main Models Without Related Records: {models_without_related}")
        print(
            f"Coverage: {coverage_percentage:.1f}% ({len(referenced_main_ids)}/{total_main})"
        )

        print("\nCardinality (related records per main model):")
        print(f"  Average: {cardinality_stats['avg']:.2f}")
        print(f"  Min: {cardinality_stats['min']}")
        print(f"  Max: {cardinality_stats['max']}")

        print(f"\nTop {limit} Distribution:")
        for i, item in enumerate(formatted_distribution, 1):
            if "identifier" in item:
                print(f"  {i}. {item['identifier']}: {item['count']} records")
            else:
                print(f"  {i}. ID {item['id']}: {item['count']} records")

        return {
            "distribution": formatted_distribution,
            "models_without_related": models_without_related,
            "cardinality": cardinality_stats,
            "coverage": {
                "referenced_count": len(referenced_main_ids),
                "total_count": total_main,
                "percentage": coverage_percentage,
            },
        }


    def analyze_m2m_relationship(
        model: Type[models.Model],
        related_model: Type[models.Model],
        relation_name: str,
        is_reverse: bool,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Analyze a ManyToMany relationship."""
        model_name = model.__name__
        related_model_name = related_model.__name__

        # For M2M relationships, we need different queries
        if is_reverse:
            # Reverse M2M (model is on the "related_name" side)
            count_field = relation_name
            target_field = "id"
            source_model = related_model
            target_model = model
        else:
            # Regular M2M (model has the M2M field)
            count_field = "id"
            target_field = relation_name
            source_model = model
            target_model = related_model

        # Count how many target items each source item relates to
        source_distribution = source_model.objects.annotate(
            relation_count=models.Count(target_field)
        ).values("id", "relation_count")

        # Count how many source items each target item relates to
        target_distribution = target_model.objects.annotate(
            relation_count=models.Count(count_field)
        ).values("id", "relation_count")

        # Source stats
        source_stats = {
            "total": source_model.objects.count(),
            "with_relations": source_model.objects.filter(
                **{f"{target_field}__isnull": False}
            )
            .distinct()
            .count(),
        }
        source_stats["without_relations"] = (
            source_stats["total"] - source_stats["with_relations"]
        )
        source_stats["coverage"] = (
            (source_stats["with_relations"] / source_stats["total"] * 100)
            if source_stats["total"] > 0
            else 0
        )

        # Target stats
        target_stats = {
            "total": target_model.objects.count(),
            "with_relations": target_model.objects.filter(
                **{f"{count_field}__isnull": False}
            )
            .distinct()
            .count(),
        }
        target_stats["without_relations"] = (
            target_stats["total"] - target_stats["with_relations"]
        )
        target_stats["coverage"] = (
            (target_stats["with_relations"] / target_stats["total"] * 100)
            if target_stats["total"] > 0
            else 0
        )

        # Calculate cardinality statistics
        source_cardinality = source_distribution.aggregate(
            avg=models.Avg("relation_count"),
            min=models.Min("relation_count"),
            max=models.Max("relation_count"),
        )

        target_cardinality = target_distribution.aggregate(
            avg=models.Avg("relation_count"),
            min=models.Min("relation_count"),
            max=models.Max("relation_count"),
        )

        # Print the results in a readable format
        print("\n=== MANY-TO-MANY RELATIONSHIP ANALYSIS RESULTS ===")

        print(f"\n{source_model.__name__} Stats:")
        print(f"  Total: {source_stats['total']}")
        print(
            f"  With relations: {source_stats['with_relations']} ({source_stats['coverage']:.1f}%)"
        )
        print(f"  Without relations: {source_stats['without_relations']}")

        print(f"\n{target_model.__name__} Stats:")
        print(f"  Total: {target_stats['total']}")
        print(
            f"  With relations: {target_stats['with_relations']} ({target_stats['coverage']:.1f}%)"
        )
        print(f"  Without relations: {target_stats['without_relations']}")

        print(
            f"\nCardinality ({source_model.__name__} to {target_model.__name__}):"
        )
        print(
            f"  Average: {source_cardinality['avg']:.2f} {target_model.__name__} per {source_model.__name__}"
        )
        print(f"  Min: {source_cardinality['min']}")
        print(f"  Max: {source_cardinality['max']}")

        print(
            f"\nCardinality ({target_model.__name__} to {source_model.__name__}):"
        )
        print(
            f"  Average: {target_cardinality['avg']:.2f} {source_model.__name__} per {target_model.__name__}"
        )
        print(f"  Min: {target_cardinality['min']}")
        print(f"  Max: {target_cardinality['max']}")

        return {
            "source_stats": source_stats,
            "target_stats": target_stats,
            "source_cardinality": source_cardinality,
            "target_cardinality": target_cardinality,
        }
    return (analyze_relationships,)


@app.cell(hide_code=True)
def _(Optional, QuerySet, Union, connection, pl):
    def queryset_to_pl(
        query: Union[QuerySet, str],
        conn=None,
        drop_id: bool = False,
        drop_columns: Optional[list] = None,
    ) -> pl.DataFrame:
        """
        Convert a Django QuerySet or SQL string to a Polars DataFrame.

        This function provides a bridge between Django's ORM and Polars, allowing you
        to leverage Polars' powerful data analysis capabilities on your Django data.

        Parameters:
        -----------
        query : Union[QuerySet, str]
            Django QuerySet or raw SQL string
            Examples:
              - User.objects.all()
              - User.objects.filter(is_active=True).select_related('profile')
              - "SELECT id, username FROM auth_user WHERE is_active = TRUE"

        conn : Any, optional
            Database connection to use (defaults to Django's connection)

        drop_id : bool, default=False
            Whether to drop the 'id' column from the resulting DataFrame

        drop_columns : list, optional
            List of additional column names to drop from the DataFrame
            Example: ['created_at', 'updated_at']

        Returns:
        --------
        pl.DataFrame
            Polars DataFrame containing the query results

        Example Usage:
        --------------
        ```python
        # Convert a QuerySet to a Polars DataFrame
        from myapp.models import Product

        # Basic conversion
        products_df = queryset_to_pl(Product.objects.all())

        # With column filtering
        products_df = queryset_to_pl(
            Product.objects.filter(in_stock=True),
            drop_id=True,
            drop_columns=['created_at', 'updated_at']
        )

        # Using raw SQL
        sql = "SELECT id, name, price FROM myapp_product WHERE price > 100"
        products_df = queryset_to_pl(sql)
        ```

        Tips:
        -----
        - For better performance with large datasets, use `.only()` in your QuerySet
          to select only the fields you need
        - Raw SQL can be more efficient for complex queries
        - After conversion, you can use all of Polars' data manipulation functions

        Based on:
        ---------
            - https://github.com/fkromer/django-polars/blob/e0ed7f8f0e8ef3eac38c517cd4de3b359ea01cac/django_polars/io.py
        """
        # Use provided connection or Django's default
        conn = conn or connection

        # Determine if we need to get a cursor or use the connection directly
        if hasattr(conn, "cursor"):
            cursor = conn.cursor()
        else:
            cursor = conn

        # Convert QuerySet to SQL or use provided SQL
        if isinstance(query, QuerySet):
            sql = str(query.query)
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            data = cursor.fetchall()
            df = pl.DataFrame(data, schema=columns)
        else:
            # For raw SQL, try to use Polars' read_database if available
            try:
                df = pl.read_database(query=query, connection=conn)
            except (AttributeError, ImportError):
                # Fallback to manual execution
                cursor.execute(query)
                columns = [col[0] for col in cursor.description]
                data = cursor.fetchall()
                df = pl.DataFrame(data, schema=columns)

        # Drop specified columns
        if drop_id and "id" in df.columns:
            df = df.drop("id")

        if drop_columns:
            drop_cols = [col for col in drop_columns if col in df.columns]
            if drop_cols:
                df = df.drop(drop_cols)

        return df
    return (queryset_to_pl,)


@app.cell
def _():
    return


@app.cell
def _():
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ## Examples of Using the Analysis Tools

    Below are practical examples of how to use the tools provided in this notebook. These examples will help you understand how to apply these functions to your own Django project.
    """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ### Example 1: Analyzing Model Relationships

    The `analyze_relationships` function helps you understand how your models are connected. The example below analyzes the relationship between `LogEntry` and its `users`.
    """
    )
    return


@app.cell
def _():
    from django.contrib.admin.models import LogEntry
    return (LogEntry,)


@app.cell
def _(LogEntry, analyze_relationships):
    # Analyze the relationship between LogEntry and its users
    analyze_relationships(LogEntry, "user")
    return


@app.cell
def _():
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ### Example 2: Converting QuerySets to Polars DataFrames

    The `queryset_to_pl` function converts Django QuerySets to Polars DataFrames, enabling powerful data analysis. The example below shows how to convert a basic queryset and examine the resulting DataFrame.
    """
    )
    return


@app.cell
def _(LogEntry, queryset_to_pl):
    df = queryset_to_pl(LogEntry.objects.all())

    print(f"DataFrame shape: {df.shape}")
    print("Columns:")
    for i in df.columns:
        print(f"\t- {i}")
    return


@app.cell
def _():
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ### Example 3: Measuring Query Performance

    The `query_performance` decorator helps you identify and optimize slow database queries. The example below demonstrates how to use it to analyze the performance of fetching data from the DigitalObject model.
    """
    )
    return


@app.cell
def _(LogEntry, query_performance):
    @query_performance(show_queries=True)
    def display_digital_objects():
        """
        Fetch all LogEntry records and display their usernames and actions.
        This function is decorated with query_performance to analyze its database efficiency.
        """
        for obj in list(LogEntry.objects.all()):
            print(f"{obj.object_repr}: {obj.change_message}")
        return "Completed displaying all actions"


    # Run the function to see performance metrics
    display_digital_objects()
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
