import os

def fix_file(path):
    try:
        with open(path, 'rb') as f:
            content = f.read()
        if b'\x00' in content:
            print(f"Purging nulls from: {path}")
            new_content = content.replace(b'\x00', b'')
            with open(path, 'wb') as f:
                f.write(new_content)
    except Exception as e:
        print(f"Error on {path}: {e}")

for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))
