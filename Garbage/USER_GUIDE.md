# 📊 Attendance Analysis System - User Guide

## 🚀 Quick Start Guide

This system automatically processes attendance data from Excel files and generates comprehensive reports with charts and monthly breakdowns.

### **Option 1: Simple Local Processing (Recommended for most users)**

1. **Place your Excel file** in the `original` folder
   - File should be named like `REPORT_2025.xlsx` or `REPORT_MARCH_2025.xlsx`
   - If the `original` folder doesn't exist, it will be created automatically

2. **Double-click the appropriate script:**
   - **Mac/Linux users**: Double-click `generate_report.sh`

3. **Wait for completion** - The script will show progress and results

4. **Find your reports** in the `analysis` folder

---

### **Option 2: Network-Aware Processing (For centralized Excel files)**

If your Excel file is stored on a network drive or shared location:

1. **Configure network settings** by editing `config_network.ini`:
   ```ini
   [Network]
   # Set your network path here:
   excel_source_path = \\server\shared\attendance_reports
   # OR for Mac: excel_source_path = /Volumes/shared/attendance_reports
   ```

2. **Run the network script:**
   - **Mac/Linux**: Double-click `generate_report_network.sh`

---

## 📁 What Gets Generated

After running the analysis, you'll find these files in the `analysis` folder:

### **📋 Main Reports (CSV format)**
- `attendance_analysis_results.csv` - Employees with problematic attendance patterns
- `comprehensive_attendance_report.csv` - Complete overview of all employees
- `non_problematic_employees.csv` - List of employees with good attendance
- `monthly_summary_report.csv` - Summary of issues by month

### **📅 Monthly Reports**
- `monthly_report_2025_03_march.csv` - March 2025 detailed analysis
- `monthly_report_2025_04_april.csv` - April 2025 detailed analysis
- `monthly_report_2025_05_may.csv` - May 2025 detailed analysis
- `monthly_report_2025_06_june.csv` - June 2025 detailed analysis

### **📊 Interactive Charts (HTML format)**
- `attendance_analysis_report.html` - Complete interactive dashboard
- `top_problematic_employees.html` - Top problematic employees chart
- `employee_infractions_chart.html` - Breakdown of issue types
- `employee_distribution.html` - Distribution of problematic patterns
- `monthly_trends.html` - Monthly trend analysis
- `monthly_top_employees_trends.html` - Employee trends by month
- `monthly_issue_breakdown.html` - Issue types by month

### **📝 Log Files**
- `analysis.log` - Detailed processing log for troubleshooting

---

### **Analysis fails partway through**
- **Check**: `analysis.log` file for detailed error messages
- **Common fix**: Ensure Excel file isn't corrupted or password-protected

---

## 🎯 Understanding the Results

### **Problematic Attendance Patterns**
The system identifies employees with multiple issues on the same day:
- **Late arrivals** or missing stand-up meetings
- **Early departures** before assigned time
- **Absent during spot-checks** (lunch monitoring)

### **Percentages Explained**
- **Problematic Percentage**: % of workdays with multiple issues
- **Non-Problematic Percentage**: % of workdays with good attendance

### **Monthly Analysis**
- Shows trends over time
- Identifies peak problem periods
- Compares employee performance across months

---

## 🔧 Customization Options

### **Changing Folder Locations**
Edit `config.ini` to use different folder names:
```ini
[Paths]
original = my_excel_files
output = temp_processing
final = consolidated_data
analysis = my_reports
```

### **Network Setup**
For organizations with centralized Excel files, modify `config_network.ini`:
```ini
[Network]
excel_source_path = \\your-server\attendance\reports
copy_to_local = true
excel_file_pattern = REPORT_*.xlsx
```
