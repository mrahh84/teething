import json
import subprocess
import threading
import time
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


# Global variables to track job status
job_status = {
    'is_running': False,
    'current_loop': None,
    'progress': 0,
    'total_items': 0,
    'processed_items': 0,
    'start_time': None,
    'end_time': None,
    'status_message': 'Ready'
}


def index(request):
    """Main page with the interface for running loops"""
    return render(request, 'enslaver_processor/index.html')


@csrf_exempt
@require_http_methods(["POST"])
def run_loop(request):
    """Start a loop execution"""
    global job_status
    
    if job_status['is_running']:
        return JsonResponse({
            'success': False,
            'message': 'A job is already running'
        })
    
    try:
        data = json.loads(request.body)
        loop_type = data.get('loop_type', 'all')
        batch_size = data.get('batch_size', 1000)
        
        # Reset job status
        job_status.update({
            'is_running': True,
            'current_loop': loop_type,
            'progress': 0,
            'total_items': 0,
            'processed_items': 0,
            'start_time': time.time(),
            'end_time': None,
            'status_message': f'Starting {loop_type} loop...'
        })
        
        # Start the job in a background thread
        thread = threading.Thread(
            target=run_management_command,
            args=(loop_type, batch_size)
        )
        thread.daemon = True
        thread.start()
        
        return JsonResponse({
            'success': True,
            'message': f'Started {loop_type} loop',
            'job_id': int(time.time())
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


def run_management_command(loop_type, batch_size):
    """Run the Django management command in background"""
    global job_status
    
    try:
        # Build the command
        cmd = ['python', 'manage.py', 'index_enslaver_data', 
               '--loop', loop_type, '--batch-size', str(batch_size)]
        
        # Run the command and capture output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Monitor the output for progress updates
        for line in process.stdout:
            if 'Processed' in line:
                # Extract progress information
                try:
                    parts = line.split()
                    processed = int(parts[1].split('/')[0])
                    total = int(parts[1].split('/')[1])
                    job_status['processed_items'] = processed
                    job_status['total_items'] = total
                    job_status['progress'] = (processed / total) * 100
                    job_status['status_message'] = f'Processed {processed}/{total} items'
                except:
                    pass
            elif 'completed' in line.lower():
                job_status['status_message'] = line.strip()
        
        # Wait for completion
        process.wait()
        
        # Update final status
        job_status.update({
            'is_running': False,
            'end_time': time.time(),
            'progress': 100,
            'status_message': f'{loop_type.title()} loop completed successfully!'
        })
        
    except Exception as e:
        job_status.update({
            'is_running': False,
            'end_time': time.time(),
            'status_message': f'Error: {str(e)}'
        })


def get_status(request):
    """Get the current job status"""
    global job_status
    
    # Calculate duration if running
    duration = None
    if job_status['start_time']:
        if job_status['end_time']:
            duration = job_status['end_time'] - job_status['start_time']
        elif job_status['is_running']:
            duration = time.time() - job_status['start_time']
    
    return JsonResponse({
        'is_running': job_status['is_running'],
        'current_loop': job_status['current_loop'],
        'progress': job_status['progress'],
        'total_items': job_status['total_items'],
        'processed_items': job_status['processed_items'],
        'status_message': job_status['status_message'],
        'duration': round(duration, 2) if duration else None,
        'start_time': job_status['start_time'],
        'end_time': job_status['end_time']
    })
