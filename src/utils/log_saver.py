import sys
import os
from datetime import datetime

class DualLogger:
    def __init__(self, filepath="execution_logs.log"):
        self.terminal = sys.stdout
        self.log_file = open(filepath, "a", encoding="utf-8") # 'a' for append
        
        # Add a separator line whenever we start a new run
        self.log_file.write(f"\n{'='*50}\nRUN STARTED: {datetime.now()}\n{'='*50}\n")

    def write(self, message):
        self.terminal.write(message) # Print to screen
        self.log_file.write(message) # Print to file
        self.log_file.flush()        # Save immediately (don't buffer)

    def flush(self):
        # Needed for python compatibility
        self.terminal.flush()
        self.log_file.flush()

def start_logging():
    # Redirect standard output (print) to our DualLogger
    sys.stdout = DualLogger()
    # Redirect errors to the same file so you catch crashes too
    sys.stderr = sys.stdout