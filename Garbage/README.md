# Attendance Analysis System

This system processes attendance data from Excel sheets and generates analysis reports to identify problematic attendance patterns.

## Configuration

The system uses a centralized configuration file (`config.ini`) to manage directory paths and script execution workflow. This makes the system more maintainable and allows for easy customization without modifying the source code.

### Configuration File Structure

The `config.ini` file contains two main sections:

#### [Paths] Section
Defines the directory names used throughout the system:
```ini
[Paths]
original = original
output = output
final = final
analysis = analysis
```

#### [Workflow] Section
Defines the execution order of scripts when running the automated workflow:
```ini
[Workflow]
step_1 = excel_to_csv.py
step_2 = consolidate_csv.py
step_3 = analyze_attendance.py
step_4 = cleanup.py
```

### Customizing the Configuration

You can customize the system behavior by editing the `config.ini` file:

1. **Change Directory Names**: Modify the values in the `[Paths]` section to use different folder names
2. **Modify Workflow**: Change the order of scripts or replace them with custom scripts in the `[Workflow]` section

**Example**: To use different directory names:
```ini
[Paths]
original = source_files
output = temp_data
final = processed_data
analysis = reports
```

All scripts will automatically use these new directory names without requiring any code changes.

## Folder Structure

- `/original` - Place the Excel files here (e.g., REPORT_MARCH_2025.xlsx) *(configurable)*
- `/output` - CSV files will be saved here (one per Excel sheet) *(configurable)*
- `/final` - The consolidated and sorted data will be saved here *(configurable)*
- `/analysis` - Analysis results and visualizations will be saved here *(configurable)*

## Setup and Usage

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Place your Excel file(s) in the `/original` folder

3. Run the analysis either as a complete workflow or step by step:

   ### Option 1: Complete Automated Workflow

   Run the master script to execute all steps in sequence:
   ```
   python run_analysis.py
   ```
   
   This will:
   - Convert Excel files to CSV
   - Consolidate the CSV files
   - Analyze attendance patterns
   - Clean up temporary files

   #### Command-Line Options

   The `run_analysis.py` script supports the following command-line arguments:

   **`--force`**: Skip confirmation prompts and run the workflow automatically
   ```bash
   python run_analysis.py --force
   ```

   **`--config`**: Specify a custom configuration file (default: `config.ini`)
   ```bash
   python run_analysis.py --config my_custom_config.ini
   ```

   **Combined usage**: You can combine both arguments
   ```bash
   python run_analysis.py --force --config production.ini
   ```

   **Help**: View all available options
   ```bash
   python run_analysis.py --help
   ```

   ### Option 2: Step-by-Step Execution

   a. Convert Excel to CSV:
   ```
   python excel_to_csv.py
   ```

   b. Consolidate the CSV files:
   ```
   python consolidate_csv.py
   ```

   c. Analyze attendance patterns:
   ```
   python analyze_attendance.py
   ```

   d. Clean up temporary CSV files (optional):
   ```
   python cleanup.py
   ```

## Analysis Methods

The system uses two complementary methods to analyze attendance patterns:

1. **Standard Analysis**: Tracks individual occurrences of problematic behavior (late arrivals, early departures, and spot-check absences) and calculates a comprehensive problematic percentage for each employee.

2. **Alternative Analysis**: Focuses specifically on employees who have multiple issues on the same day. This method is more forgiving as it doesn't count absences against employees, but flags days where an employee had multiple attendance problems.

### Analysis Outputs

For each method, the system generates:

- CSV files with detailed results
- Visualizations highlighting the most problematic employees
- Summary statistics in the console output

## Analysis Output

The analysis script generates:

1. A CSV file with attendance metrics for each employee
2. Visualizations showing problematic attendance patterns
3. Console output with high-level statistics
4. A detailed execution log (`analysis.log`) in the root directory for troubleshooting and audit purposes

**Note**: The `analysis.log` file contains comprehensive logging information including debug details, error messages, and execution timestamps. This log file can be invaluable for troubleshooting issues or understanding the complete execution flow of the analysis workflow.

## Problematic Patterns Tracked

The system tracks the following attendance issues:

- Late arrivals/missing stand-up meetings
- Early departures (before assigned times)
- Absences during spot-checks

## Customization

You can customize column names and problematic values by editing the settings at the top of each script.

## Automatic Cleanup

There are two ways to clean up the temporary CSV files:

1. **Manual cleanup**: Run `python cleanup.py` after analysis to remove all temporary CSV files.
   - This will prompt for confirmation before deleting files.
   - Use `python cleanup.py --force` to skip the confirmation prompt.

2. **Automatic cleanup**: Edit the `analyze_attendance.py` file and set `auto_cleanup = True` to automatically clean up temporary files after analysis completes.

The cleanup process only removes CSV files from the `/output` directory. The following are preserved:
- Original Excel files in the `/original` directory
- Consolidated data in the `/final` directory
- Analysis results in the `/analysis` directory 