import marimo

__generated_with = "0.12.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import httpx
    from pydantic import BaseModel
    import polars as pl
    import plotly
    return BaseModel, httpx, mo, pl, plotly


@app.cell
def _():
    url = "url string"
    return (url,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # Visualization Exploration

        This notebook will be used to explore the data within the database and create valuable visualizations and other insights from the data within the app.

        It is **not** a polished report, but a way to explore what should be included in such a report.
        """
    )
    return


if __name__ == "__main__":
    app.run()
