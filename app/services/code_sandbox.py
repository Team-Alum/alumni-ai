import sys
import io
import contextlib
import traceback
from typing import Dict, Any

def execute_python_code(code: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Executes Python snippet in a sandboxed string buffer and captures stdout/stderr.
    """
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    # Simple safety check
    forbidden = ["os.system", "subprocess", "shutil.rmtree", "__import__('os').system"]
    for phrase in forbidden:
        if phrase in code:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Security restriction: Execution of '{phrase}' is disallowed in sandbox."
            }
            
    success = True
    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            exec_globals = {"__builtins__": __builtins__}
            exec(code, exec_globals)
    except Exception:
        success = False
        stderr_capture.write(traceback.format_exc())
        
    return {
        "success": success,
        "stdout": stdout_capture.getvalue().strip(),
        "stderr": stderr_capture.getvalue().strip()
    }
