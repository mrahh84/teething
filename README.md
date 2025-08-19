# Enslaver Data Processor

A Django-based web application for processing enslaver data with individual loop control, real-time progress monitoring, and a modern web interface.

## Features

- **Individual Loop Control**: Run voyages loop, roles loop, or both together
- **Real-time Progress Monitoring**: Live progress bars and status updates
- **Modern Web Interface**: Responsive design with real-time updates
- **Background Processing**: Long-running operations don't block the web interface
- **Configurable Batch Sizes**: Adjustable batch processing for performance tuning
- **Progress Bars**: Visual progress indicators using tqdm

## Project Structure

```
thething/
├── manage.py                          # Django management script
├── requirements.txt                   # Python dependencies
├── index_enslaver_data.py            # Enhanced management command
├── thething/                         # Django project settings
│   ├── __init__.py
│   ├── settings.py                   # Django configuration
│   ├── urls.py                       # Main URL routing
│   └── wsgi.py                       # WSGI configuration
├── enslaver_processor/               # Custom Django app
│   ├── __init__.py
│   ├── apps.py                       # App configuration
│   ├── urls.py                       # App URL routing
│   └── views.py                      # Web interface views
└── templates/                        # HTML templates
    └── enslaver_processor/
        └── index.html                # Main web interface
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Django Migrations

```bash
python manage.py migrate
```

### 3. Start the Development Server

```bash
python manage.py runserver
```

### 4. Access the Web Interface

Open your browser and navigate to: `http://127.0.0.1:8000/`

## Usage

### Web Interface

1. **Select Loop Type**: Choose between running all loops, just voyages, or just roles
2. **Set Batch Size**: Configure the batch size for progress reporting (default: 1000)
3. **Run Processing**: Click "Run Selected Loop" to start processing
4. **Monitor Progress**: Watch real-time progress bars and status updates
5. **View Results**: See completion status and processing details

### Command Line Interface

You can also run the processing directly from the command line:

```bash
# Run all loops
python manage.py index_enslaver_data

# Run only voyages loop
python manage.py index_enslaver_data --loop voyages

# Run only roles loop
python manage.py index_enslaver_data --loop roles

# Customize batch size
python manage.py index_enslaver_data --batch-size 500
```

## Loop Types

### 1. Voyages Loop
- Processes enslaver-voyage relationships
- Associates enslavers with their related voyages
- Optimizes search performance for voyage-based queries

### 2. Roles Loop
- Processes enslaver-role relationships
- Associates enslavers with their roles
- Optimizes search performance for role-based queries

### 3. Third Loop (Coming Soon)
- Placeholder for future functionality
- Ready for implementation when needed

## Technical Details

### Progress Monitoring
- Uses `tqdm` library for progress bars
- Real-time status updates via AJAX
- Background thread processing for non-blocking operation

### Performance Features
- Prefetch related objects to minimize database queries
- Batch processing with configurable sizes
- Efficient database operations using Django ORM

### Web Interface Features
- Responsive design that works on all devices
- Real-time status updates without page refresh
- Modern UI with smooth animations and transitions
- Error handling and user feedback

## Customization

### Adding a Third Loop

To implement the third loop, modify the `index_enslaver_data.py` file:

1. Add the loop option to the choices in `add_arguments`:
```python
choices=['voyages', 'roles', 'third', 'all']
```

2. Add the loop execution logic in the `handle` method:
```python
if loop_type in ['third', 'all']:
    self.stdout.write(self.style.SUCCESS('Running third loop...'))
    self.run_third_loop(batch_size)
```

3. Implement the `run_third_loop` method with your specific logic

### Modifying Batch Sizes

Adjust the default batch size in the management command or web interface to optimize performance for your specific dataset and server capabilities.

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all required packages are installed via `pip install -r requirements.txt`
2. **Database Errors**: Run `python manage.py migrate` to set up the database
3. **Permission Errors**: Ensure the application has write access to the project directory

### Performance Tuning

- Adjust batch sizes based on your server's memory and processing capabilities
- Monitor database performance during large operations
- Consider running during off-peak hours for production systems

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
