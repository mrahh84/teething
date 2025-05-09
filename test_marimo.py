import marimo as mo
import io

def test_marimo():
    app = mo.App()
    
    @app.cell
    def hello():
        return mo.md('# Hello World')
    
    # Run the app
    app.run()
    
    # Test the as_html function
    try:
        if hasattr(mo, 'as_html'):
            html_obj = mo.as_html(app)
            print("Type of html:", type(html_obj))
            
            # Try different ways to get string content
            str_repr = str(html_obj)
            html_attr = getattr(html_obj, "html", None) if hasattr(html_obj, "html") else None
            to_html = getattr(html_obj, "to_html", None)() if hasattr(html_obj, "to_html") else None
            
            result = f"as_html object: {type(html_obj)}\n"
            result += f"- str representation: {str_repr[:30]}...\n"
            result += f"- html attribute: {html_attr[:30] if html_attr else 'None'}...\n"
            result += f"- to_html method: {to_html[:30] if to_html else 'None'}..."
            
            # Check if Html is callable
            if callable(html_obj):
                try:
                    called_result = html_obj()
                    result += f"\n- called result: {str(called_result)[:30]}..."
                except Exception as call_err:
                    result += f"\n- called result error: {str(call_err)}"
                
            return True, result
        
        return False, "as_html not found"
    except Exception as e:
        return False, f"Error using as_html: {str(e)}"

success, result = test_marimo()
print(f"Success: {success}")
print(f"Result:\n{result}")

# Check attributes of Html class
if hasattr(mo, 'Html'):
    print("\nAttributes of Html class:")
    for attr in dir(mo.Html):
        if not attr.startswith('_'):
            print(f"- {attr}")

# Check the signature of as_html
if hasattr(mo, 'as_html'):
    import inspect
    print("\nas_html signature:", inspect.signature(mo.as_html))

# Check more marimo functions
print("\nAvailable functions in marimo:")
for name in dir(mo):
    if not name.startswith('_') and (name.lower().find('html') >= 0 or name.lower().find('export') >= 0):
        print(f"- {name}") 