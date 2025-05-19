#!/usr/bin/env python
"""
Generate a secure Django secret key.
Run this script to generate a new SECRET_KEY for use in .env file.
"""

import secrets
import string


def generate_secret_key(length=50):
    """Generate a secure random string for Django's SECRET_KEY setting."""
    chars = string.ascii_letters + string.digits + string.punctuation
    # Filter out characters that could cause issues in .env files
    chars = chars.replace("'", "").replace('"', "").replace('\\', "")
    return ''.join(secrets.choice(chars) for _ in range(length))


if __name__ == "__main__":
    print("\nGenerated Django SECRET_KEY:")
    print("-" * 60)
    print(generate_secret_key())
    print("-" * 60)
    print("\nAdd this key to your .env file:")
    print('SECRET_KEY=your-generated-key\n') 