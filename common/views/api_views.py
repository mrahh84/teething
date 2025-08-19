"""
REST API views (class-based views).

This module contains all DRF-based API endpoints for the attendance system.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from django.db.models import Q, Count, Avg
from datetime import datetime, timedelta, date, timezone, time
import json

from ..models import (
    Employee, Event, EventType, Location, AttendanceRecord, Card, Department,
    AnalyticsCache, ReportConfiguration, EmployeeAnalytics, DepartmentAnalytics, SystemPerformance,
    TaskAssignment, LocationMovement, LocationAnalytics
)
from ..serializers import (
    EmployeeSerializer,
    EventSerializer,
    LocationSerializer,
    SingleEventSerializer,
    DepartmentSerializer,
    AnalyticsCacheSerializer,
    ReportConfigurationSerializer,
    EmployeeAnalyticsSerializer,
    DepartmentAnalyticsSerializer,
    SystemPerformanceSerializer,
)
from ..permissions import SecurityPermission, AttendancePermission, ReportingPermission, AdminPermission


class SingleEventView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Event.
    Requires authentication for creating, updating or deleting.
    Uses PrimaryKeyRelatedFields for related objects during updates.
    """

    authentication_classes = [SessionAuthentication]  # Or TokenAuthentication, etc.
    permission_classes = [SecurityPermission]  # Security can view events
    serializer_class = SingleEventSerializer
    queryset = Event.objects.all()
    lookup_field = "id"


class SingleLocationView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Location.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [SecurityPermission]  # Security can view locations
    serializer_class = LocationSerializer
    queryset = Location.objects.all()
    lookup_field = "id"


class SingleEmployeeView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Employee.
    Requires authentication for creating, updating or deleting.
    Uses EmployeeSerializer which provides detailed info for retrieve
    and accepts IDs for related fields during updates.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AdminPermission]  # Only admin can manage employees
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.all()
    lookup_field = "id"


class ListEventsView(generics.ListAPIView):
    """
    API endpoint for listing all Events.
    Requires authentication for creating, updating or deleting.
    Shows nested details of related objects.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [SecurityPermission]  # Security can view events
    serializer_class = EventSerializer  # Use the detailed serializer for listing
    queryset = (
        Event.objects.all()
        .select_related(  # Optimize query
            "event_type", "employee", "location", "created_by"
        )
        .order_by("-timestamp")
    )


class ListDepartmentsView(generics.ListAPIView):
    """
    API endpoint for listing all Departments.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting can view departments
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()


class SingleDepartmentView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Department.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AdminPermission]  # Only admin can manage departments
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
    lookup_field = "id"


class ListAnalyticsCacheView(generics.ListAPIView):
    """
    API endpoint for listing AnalyticsCache entries.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can view analytics cache
    serializer_class = AnalyticsCacheSerializer
    queryset = AnalyticsCache.objects.all()


class SingleAnalyticsCacheView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single AnalyticsCache entry.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can manage analytics cache
    serializer_class = AnalyticsCacheSerializer
    queryset = AnalyticsCache.objects.all()
    lookup_field = "id"


class ListReportConfigurationsView(generics.ListAPIView):
    """
    API endpoint for listing ReportConfiguration entries.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can view report configurations
    serializer_class = ReportConfigurationSerializer
    queryset = ReportConfiguration.objects.all()

    def get_queryset(self):
        return ReportConfiguration.objects.all()


class SingleReportConfigurationView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single ReportConfiguration entry.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can manage report configurations
    serializer_class = ReportConfigurationSerializer
    queryset = ReportConfiguration.objects.all()
    lookup_field = "id"

    def get_queryset(self):
        return ReportConfiguration.objects.all()


class ListEmployeeAnalyticsView(generics.ListAPIView):
    """
    API endpoint for listing EmployeeAnalytics entries.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can view employee analytics
    serializer_class = EmployeeAnalyticsSerializer
    queryset = EmployeeAnalytics.objects.all()

    def get_queryset(self):
        queryset = EmployeeAnalytics.objects.all()
        
        # Filter by employee if specified
        employee_id = self.request.query_params.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        
        # Filter by date range if specified
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(
                    date__gte=start,
                    date__lte=end
                )
            except ValueError:
                pass
        
        # Filter by department if specified
        department = self.request.query_params.get('department')
        if department:
            queryset = queryset.filter(employee__department__name__icontains=department)
        
        return queryset.select_related('employee', 'employee__department').order_by('-date')


class SingleEmployeeAnalyticsView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single EmployeeAnalytics entry.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can manage employee analytics
    serializer_class = EmployeeAnalyticsSerializer
    queryset = EmployeeAnalytics.objects.all()
    lookup_field = "id"


class ListDepartmentAnalyticsView(generics.ListAPIView):
    """
    API endpoint for listing DepartmentAnalytics entries.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can view department analytics
    serializer_class = DepartmentAnalyticsSerializer
    queryset = DepartmentAnalytics.objects.all()

    def get_queryset(self):
        queryset = DepartmentAnalytics.objects.all()
        
        # Filter by department if specified
        department_id = self.request.query_params.get('department_id')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        # Filter by date range if specified
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(
                    date__gte=start,
                    date__lte=end
                )
            except ValueError:
                pass
        
        return queryset.select_related('department').order_by('-date')


class SingleDepartmentAnalyticsView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single DepartmentAnalytics entry.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can manage department analytics
    serializer_class = DepartmentAnalyticsSerializer
    queryset = DepartmentAnalytics.objects.all()
    lookup_field = "id"


class ListSystemPerformanceView(generics.ListAPIView):
    """
    API endpoint for listing SystemPerformance entries.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AdminPermission]  # Only admin can view system performance
    serializer_class = SystemPerformanceSerializer
    queryset = SystemPerformance.objects.all()

    def get_queryset(self):
        queryset = SystemPerformance.objects.all()
        
        # Filter by date range if specified
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(
                    date__gte=start,
                    date__lte=end
                )
            except ValueError:
                pass
        
        # Filter by metric type if specified
        metric_type = self.request.query_params.get('metric_type')
        if metric_type:
            queryset = queryset.filter(metric_type=metric_type)
        
        return queryset.order_by('-date')


class SingleSystemPerformanceView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single SystemPerformance entry.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AdminPermission]  # Only admin can manage system performance
    serializer_class = SystemPerformanceSerializer
    queryset = SystemPerformance.objects.all()
    lookup_field = "id"


class RealTimeEmployeeStatusView(generics.ListAPIView):
    """API endpoint for real-time employee status data"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]
    serializer_class = EmployeeSerializer

    def get_queryset(self):
        return Employee.objects.filter(is_active=True).select_related('department')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['include_status'] = True
        return context


class LiveAttendanceCounterView(generics.RetrieveAPIView):
    """API endpoint for live attendance counter data"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]
    serializer_class = EmployeeSerializer

    def get_object(self):
        # Return a dummy object since this is for counting
        return Employee.objects.first()

    def retrieve(self, request, *args, **kwargs):
        from django.utils import timezone
        today = timezone.now().date()
        
        # Get real-time counts
        total_employees = Employee.objects.filter(is_active=True).count()
        # Use values_list to get unique employee IDs, then count them
        clocked_in = Event.objects.filter(
            event_type__name='Clock In',
            timestamp__date=today
        ).values_list('employee', flat=True).distinct().count()
        clocked_out = Event.objects.filter(
            event_type__name='Clock Out',
            timestamp__date=today
        ).values_list('employee', flat=True).distinct().count()
        
        data = {
            'total_employees': total_employees,
            'clocked_in': clocked_in,
            'clocked_out': clocked_out,
            'present_today': clocked_in - clocked_out,
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(data)


class PatternRecognitionView(generics.ListAPIView):
    """API endpoint for pattern recognition analysis"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]
    serializer_class = EmployeeAnalyticsSerializer

    def get_queryset(self):
        return EmployeeAnalytics.objects.all()

    def list(self, request, *args, **kwargs):
        analytics = self.get_queryset()
        
        # Analyze patterns
        arrival_patterns = self._analyze_arrival_patterns(analytics)
        departure_patterns = self._analyze_departure_patterns(analytics)
        location_patterns = self._analyze_location_patterns(analytics)
        anomalies = self._detect_anomalies(analytics)
        trends = self._analyze_trends(analytics)
        correlations = self._analyze_correlations(analytics)
        
        data = {
            'arrival_patterns': arrival_patterns,
            'departure_patterns': departure_patterns,
            'location_patterns': location_patterns,
            'anomalies': anomalies,
            'trends': trends,
            'correlations': correlations,
        }
        
        return Response(data)

    def _analyze_arrival_patterns(self, analytics):
        """Analyze employee arrival time patterns"""
        patterns = []
        for analytic in analytics:
            if hasattr(analytic, 'avg_arrival_time') and analytic.avg_arrival_time:
                patterns.append({
                    'employee_id': analytic.employee.id,
                    'employee_name': f"{analytic.employee.given_name} {analytic.employee.surname}",
                    'avg_arrival_time': str(analytic.avg_arrival_time),
                    'consistency_score': getattr(analytic, 'arrival_consistency', 0),
                    'trend': getattr(analytic, 'arrival_trend', 'stable')
                })
        return patterns

    def _analyze_departure_patterns(self, analytics):
        """Analyze employee departure time patterns"""
        patterns = []
        for analytic in analytics:
            if hasattr(analytic, 'avg_departure_time') and analytic.avg_departure_time:
                patterns.append({
                    'employee_id': analytic.employee.id,
                    'employee_name': f"{analytic.employee.given_name} {analytic.employee.surname}",
                    'avg_departure_time': str(analytic.avg_departure_time),
                    'consistency_score': getattr(analytic, 'departure_consistency', 0),
                    'trend': getattr(analytic, 'departure_trend', 'stable')
                })
        return patterns

    def _analyze_location_patterns(self, analytics):
        """Analyze employee location movement patterns"""
        patterns = []
        for analytic in analytics:
            if hasattr(analytic, 'frequent_locations'):
                patterns.append({
                    'employee_id': analytic.employee.id,
                    'employee_name': f"{analytic.employee.given_name} {analytic.employee.surname}",
                    'frequent_locations': getattr(analytic, 'frequent_locations', []),
                    'movement_frequency': getattr(analytic, 'movement_frequency', 0),
                    'location_preference': getattr(analytic, 'location_preference', 'unknown')
                })
        return patterns

    def _detect_anomalies(self, analytics):
        """Detect unusual attendance patterns"""
        anomalies = []
        for analytic in analytics:
            if hasattr(analytic, 'anomaly_score') and analytic.anomaly_score > 0.7:
                anomalies.append({
                    'employee_id': analytic.employee.id,
                    'employee_name': f"{analytic.employee.given_name} {analytic.employee.surname}",
                    'anomaly_score': analytic.anomaly_score,
                    'anomaly_type': getattr(analytic, 'anomaly_type', 'unknown'),
                    'severity': 'high' if analytic.anomaly_score > 0.9 else 'medium'
                })
        return anomalies

    def _analyze_trends(self, analytics):
        """Analyze attendance trends over time"""
        trends = []
        for analytic in analytics:
            if hasattr(analytic, 'attendance_trend'):
                trends.append({
                    'employee_id': analytic.employee.id,
                    'employee_name': f"{analytic.employee.given_name} {analytic.employee.surname}",
                    'attendance_trend': analytic.attendance_trend,
                    'trend_strength': getattr(analytic, 'trend_strength', 0),
                    'prediction_confidence': getattr(analytic, 'prediction_confidence', 0)
                })
        return trends

    def _analyze_correlations(self, analytics):
        """Analyze correlations between different metrics"""
        correlations = []
        for analytic in analytics:
            if hasattr(analytic, 'correlation_data'):
                correlations.append({
                    'employee_id': analytic.employee.id,
                    'employee_name': f"{analytic.employee.given_name} {analytic.employee.surname}",
                    'correlation_data': getattr(analytic, 'correlation_data', {}),
                    'correlation_strength': getattr(analytic, 'correlation_strength', 0)
                })
        return correlations


class AnomalyDetectionView(generics.ListAPIView):
    """API endpoint for anomaly detection system"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]
    serializer_class = EmployeeAnalyticsSerializer

    def get_queryset(self):
        return EmployeeAnalytics.objects.all()

    def list(self, request, *args, **kwargs):
        analytics = self.get_queryset()
        
        # Detect anomalies
        anomalies = []
        for analytic in analytics:
            if hasattr(analytic, 'anomaly_score') and analytic.anomaly_score > 0.5:
                severity = self._calculate_anomaly_severity(analytic.anomaly_score)
                anomalies.append({
                    'employee_id': analytic.employee.id,
                    'employee_name': f"{analytic.employee.given_name} {analytic.employee.surname}",
                    'anomaly_score': analytic.anomaly_score,
                    'severity': severity,
                    'anomaly_type': getattr(analytic, 'anomaly_type', 'unknown'),
                    'detected_at': getattr(analytic, 'last_updated', None),
                    'recommendations': self._generate_anomaly_recommendations(analytic)
                })
        
        # Sort by severity (high to low)
        anomalies.sort(key=lambda x: x['anomaly_score'], reverse=True)
        
        return Response({
            'anomalies': anomalies,
            'total_anomalies': len(anomalies),
            'high_severity_count': len([a for a in anomalies if a['severity'] == 'high']),
            'medium_severity_count': len([a for a in anomalies if a['severity'] == 'medium']),
            'low_severity_count': len([a for a in anomalies if a['severity'] == 'low'])
        })

    def _calculate_anomaly_severity(self, score):
        """Calculate anomaly severity based on score"""
        if score >= 0.8:
            return 'high'
        elif score >= 0.6:
            return 'medium'
        else:
            return 'low'

    def _generate_anomaly_recommendations(self, analytic):
        """Generate recommendations based on anomaly type"""
        recommendations = []
        anomaly_type = getattr(analytic, 'anomaly_type', 'unknown')
        
        if anomaly_type == 'late_arrival':
            recommendations.append('Consider flexible start times')
            recommendations.append('Review commute patterns')
        elif anomaly_type == 'early_departure':
            recommendations.append('Review workload distribution')
            recommendations.append('Check for personal commitments')
        elif anomaly_type == 'irregular_patterns':
            recommendations.append('Schedule regular check-ins')
            recommendations.append('Review work-life balance')
        
        return recommendations


class PredictiveAnalyticsView(generics.ListAPIView):
    """API endpoint for predictive analytics"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]
    serializer_class = EmployeeAnalyticsSerializer

    def get_queryset(self):
        return EmployeeAnalytics.objects.all()

    def list(self, request, *args, **kwargs):
        analytics = self.get_queryset()
        
        # Generate predictions
        attendance_forecast = self._forecast_attendance(analytics)
        capacity_forecast = self._forecast_capacity(analytics)
        risk_assessment = self._assess_risks(analytics)
        recommendations = self._generate_recommendations(analytics)
        
        data = {
            'attendance_forecast': attendance_forecast,
            'capacity_forecast': capacity_forecast,
            'risk_assessment': risk_assessment,
            'recommendations': recommendations,
            'forecast_horizon': '30 days',
            'confidence_level': '85%'
        }
        
        return Response(data)

    def _forecast_attendance(self, analytics):
        """Forecast attendance patterns"""
        forecasts = []
        for analytic in analytics:
            if hasattr(analytic, 'attendance_trend'):
                # Simple linear prediction
                current_rate = getattr(analytic, 'attendance_rate', 0.8)
                trend = getattr(analytic, 'attendance_trend', 'stable')
                
                if trend == 'improving':
                    predicted_rate = min(1.0, current_rate * 1.05)
                elif trend == 'declining':
                    predicted_rate = max(0.0, current_rate * 0.95)
                else:
                    predicted_rate = current_rate
                
                forecasts.append({
                    'employee_id': analytic.employee.id,
                    'employee_name': f"{analytic.employee.given_name} {analytic.employee.surname}",
                    'current_attendance_rate': current_rate,
                    'predicted_attendance_rate': round(predicted_rate, 3),
                    'confidence': 0.85
                })
        
        return forecasts

    def _forecast_capacity(self, analytics):
        """Forecast capacity requirements"""
        total_employees = len(analytics)
        if total_employees == 0:
            return {}
        
        # Calculate average attendance rate
        total_rate = sum(getattr(a, 'attendance_rate', 0.8) for a in analytics)
        avg_rate = total_rate / total_employees
        
        # Forecast capacity for next 30 days
        capacity_forecast = {
            'current_capacity': total_employees,
            'predicted_capacity_7_days': int(total_employees * avg_rate * 0.98),
            'predicted_capacity_30_days': int(total_employees * avg_rate * 0.95),
            'capacity_trend': 'stable' if avg_rate > 0.8 else 'declining',
            'recommendations': []
        }
        
        if avg_rate < 0.8:
            capacity_forecast['recommendations'].append('Consider hiring additional staff')
            capacity_forecast['recommendations'].append('Review attendance policies')
        
        return capacity_forecast

    def _assess_risks(self, analytics):
        """Assess risks based on analytics data"""
        risks = []
        for analytic in analytics:
            risk_score = 0
            risk_factors = []
            
            # Attendance risk
            attendance_rate = getattr(analytic, 'attendance_rate', 0.8)
            if attendance_rate < 0.7:
                risk_score += 0.4
                risk_factors.append('Low attendance rate')
            
            # Punctuality risk
            if hasattr(analytic, 'avg_arrival_time'):
                # Add logic for late arrival risk
                pass
            
            # Pattern risk
            if hasattr(analytic, 'anomaly_score'):
                risk_score += analytic.anomaly_score * 0.3
                if analytic.anomaly_score > 0.7:
                    risk_factors.append('Irregular patterns detected')
            
            if risk_score > 0.3:
                risks.append({
                    'employee_id': analytic.employee.id,
                    'employee_name': f"{analytic.employee.given_name} {analytic.employee.surname}",
                    'risk_score': round(risk_score, 3),
                    'risk_level': 'high' if risk_score > 0.7 else 'medium' if risk_score > 0.4 else 'low',
                    'risk_factors': risk_factors
                })
        
        return risks

    def _generate_recommendations(self, analytic):
        """Generate actionable recommendations"""
        recommendations = []
        
        # Attendance recommendations
        attendance_rate = getattr(analytic, 'attendance_rate', 0.8)
        if attendance_rate < 0.7:
            recommendations.append('Implement attendance improvement plan')
            recommendations.append('Schedule regular check-ins')
        
        # Pattern recommendations
        if hasattr(analytic, 'anomaly_score') and analytic.anomaly_score > 0.6:
            recommendations.append('Investigate irregular patterns')
            recommendations.append('Provide additional support')
        
        # Performance recommendations
        if hasattr(analytic, 'performance_score'):
            performance = analytic.performance_score
            if performance < 0.7:
                recommendations.append('Provide performance coaching')
                recommendations.append('Set clear performance goals')
        
        return recommendations