import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# Read the analysis results
df = pd.read_csv('analysis/attendance_analysis_results.csv')

# Sort by problematic days in descending order
df = df.sort_values('Problematic Days', ascending=False)

# Create the bar chart
fig = go.Figure()

# Add bars for problematic percentage with color gradient
fig.add_trace(go.Bar(
    x=df['Problematic Percentage'],
    y=df['NAMES'],
    orientation='h',
    name='Problematic Percentage',
    marker=dict(
        color=df['Problematic Percentage'],
        colorscale='Reds',
        showscale=True,
        colorbar=dict(
            title='Percentage',
            x=1.1
        )
    ),
    text=df['Problematic Percentage'].round(1).astype(str) + '%',
    textposition='auto',
    hovertemplate='%{y}<br>Problematic Percentage: %{x:.1f}%<extra></extra>'
))

# Add bars for problematic days with color gradient
fig.add_trace(go.Bar(
    x=df['Problematic Days'],
    y=df['NAMES'],
    orientation='h',
    name='Problematic Days',
    marker=dict(
        color=df['Problematic Days'],
        colorscale='Teal',
        showscale=True,
        colorbar=dict(
            title='Days',
            x=1.2
        )
    ),
    text=df['Problematic Days'],
    textposition='auto',
    xaxis='x2',
    hovertemplate='%{y}<br>Problematic Days: %{x}<extra></extra>'
))

# Update layout
fig.update_layout(
    title={
        'text': 'Top Employees with Multiple Issues on Same Day',
        'y':0.95,
        'x':0.5,
        'xanchor': 'center',
        'yanchor': 'top',
        'font': {'size': 24}
    },
    xaxis_title='Percentage of Workdays with Multiple Issues',
    yaxis_title='Employee',
    xaxis=dict(
        title_font=dict(size=14),
        tickfont=dict(size=12),
        autorange='reversed'
    ),
    xaxis2=dict(
        title='Problematic Days',
        overlaying='x',
        side='top',
        title_font=dict(size=14),
        tickfont=dict(size=12)
    ),
    yaxis=dict(
        title_font=dict(size=14),
        tickfont=dict(size=12),
        automargin=True
    ),
    barmode='group',
    height=max(600, len(df) * 30),  # Dynamic height based on number of employees
    showlegend=True,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        font=dict(size=12)
    ),
    margin=dict(l=50, r=150, t=100, b=max(200, len(df) * 5)),  # Increased right margin for colorbars
    plot_bgcolor='white',
    paper_bgcolor='white',
    font=dict(family="Arial, sans-serif")
)

# Save the figure as HTML
pio.write_html(fig, 'analysis/top_problematic_employees_chart.html')

print("Chart has been generated and saved as 'analysis/top_problematic_employees_chart.html'") 