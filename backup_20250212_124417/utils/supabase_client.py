import os
from supabase import create_client

def get_supabase_client():
    """Get Supabase client instance"""
    return create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_KEY')
    ) 