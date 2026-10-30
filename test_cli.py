import subprocess, sys
proc = subprocess.run([sys.executable, 'cli.py', '--list-formats', 'https://youtu.be/dQw4w9WgXcQ'], capture_output=True, text=True)
print('returncode:', proc.returncode)
print('stdout:', proc.stdout)
print('stderr:', proc.stderr)
