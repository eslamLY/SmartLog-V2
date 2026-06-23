"""Generate a secure SECRET_KEY"""
import secrets
key = secrets.token_hex(32)
print(key)
with open(r'C:\Users\eslam\OneDrive\Desktop\SmartLog V2\secret_key.txt', 'w') as f:
    f.write(key)
