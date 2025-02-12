from setuptools import setup, find_packages

setup(
    name="holly_menus",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'Flask>=2.3.3',
        'Pillow',  # This is the PIL library
        'python-dotenv',
        'reportlab',
        'pytest',
        'pytest-mock',
        'supabase',
        'redis',
        'gunicorn',
        'requests',
        'httpx',
        'psycopg2-binary',
        'pytesseract',
    ],
) 