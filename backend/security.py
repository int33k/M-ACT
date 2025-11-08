# MACT Security Module
# Authentication, rate limiting, and input validation
import functools
import re
import os
from flask import request, jsonify
from typing import Optional, Tuple

# Admin API Key (set via environment variable)
# Accepts both ADMIN_AUTH_TOKEN (new) and MACT_ADMIN_API_KEY (legacy)
ADMIN_API_KEY = os.getenv('ADMIN_AUTH_TOKEN') or os.getenv('MACT_ADMIN_API_KEY', 'changeme-in-production')

# Allowed patterns
ROOM_CODE_PATTERN = re.compile(r'^[a-z0-9-]+$')
DEVELOPER_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
# Updated URL pattern to support IP addresses, domains with TLD, optional port, and optional path
URL_PATTERN = re.compile(r'^https?://([a-z0-9.-]+\.[a-z]{2,}|localhost|127\.0\.0\.1|0\.0\.0\.0)(:[0-9]+)?(/.*)?$', re.IGNORECASE)
COMMIT_HASH_PATTERN = re.compile(r'^[a-f0-9]{7,40}$')
BRANCH_PATTERN = re.compile(r'^[a-zA-Z0-9/_-]+$')

# Validation limits
MAX_ROOM_CODE_LENGTH = 50
MAX_DEVELOPER_ID_LENGTH = 30
MAX_COMMIT_MESSAGE_LENGTH = 200
MAX_BRANCH_LENGTH = 50

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

def validate_room_code(room_code: str) -> str:
    """
    Validate room code format and length.
    
    Rules:
    - Only lowercase letters, numbers, and hyphens
    - Max 50 characters
    - Must not start or end with hyphen
    
    Raises ValidationError if invalid.
    """
    if not room_code or not isinstance(room_code, str):
        raise ValidationError("room_code is required and must be a string")
    
    if len(room_code) > MAX_ROOM_CODE_LENGTH:
        raise ValidationError(f"room_code too long (max {MAX_ROOM_CODE_LENGTH} chars)")
    
    if not ROOM_CODE_PATTERN.match(room_code):
        raise ValidationError("room_code must contain only lowercase letters, numbers, and hyphens")
    
    if room_code.startswith('-') or room_code.endswith('-'):
        raise ValidationError("room_code cannot start or end with hyphen")
    
    return room_code.strip()

def validate_developer_id(developer_id: str) -> str:
    """
    Validate developer ID format and length.
    
    Rules:
    - Letters, numbers, underscores, and hyphens
    - Max 30 characters
    - Must not be empty
    
    Raises ValidationError if invalid.
    """
    if not developer_id or not isinstance(developer_id, str):
        raise ValidationError("developer_id is required and must be a string")
    
    if len(developer_id) > MAX_DEVELOPER_ID_LENGTH:
        raise ValidationError(f"developer_id too long (max {MAX_DEVELOPER_ID_LENGTH} chars)")
    
    if not DEVELOPER_ID_PATTERN.match(developer_id):
        raise ValidationError("developer_id must contain only letters, numbers, underscores, and hyphens")
    
    return developer_id.strip()

def validate_subdomain_url(url: str) -> str:
    """
    Validate subdomain URL format.
    
    Rules:
    - Must be valid HTTP/HTTPS URL
    - Must have domain and TLD
    - Optional port number
    
    Raises ValidationError if invalid.
    """
    if not url or not isinstance(url, str):
        raise ValidationError("subdomain_url is required and must be a string")
    
    if not URL_PATTERN.match(url):
        raise ValidationError("subdomain_url must be a valid HTTP/HTTPS URL")
    
    # Additional check: must contain "dev-" or be localhost
    if not ('dev-' in url or 'localhost' in url or '127.0.0.1' in url):
        raise ValidationError("subdomain_url should be a dev-* subdomain or localhost")
    
    return url.strip().rstrip('/')

def validate_commit_hash(commit_hash: str) -> str:
    """
    Validate Git commit hash format.
    
    Rules:
    - Hexadecimal characters only
    - 7-40 characters (short or full SHA)
    
    Raises ValidationError if invalid.
    """
    if not commit_hash or not isinstance(commit_hash, str):
        raise ValidationError("commit_hash is required and must be a string")
    
    if not COMMIT_HASH_PATTERN.match(commit_hash):
        raise ValidationError("commit_hash must be a valid Git SHA (7-40 hex chars)")
    
    return commit_hash.strip().lower()

def validate_branch(branch: str) -> str:
    """
    Validate Git branch name.
    
    Rules:
    - Letters, numbers, slashes, underscores, hyphens
    - Max 50 characters
    
    Raises ValidationError if invalid.
    """
    if not branch or not isinstance(branch, str):
        raise ValidationError("branch is required and must be a string")
    
    if len(branch) > MAX_BRANCH_LENGTH:
        raise ValidationError(f"branch too long (max {MAX_BRANCH_LENGTH} chars)")
    
    if not BRANCH_PATTERN.match(branch):
        raise ValidationError("branch contains invalid characters")
    
    return branch.strip()

def validate_commit_message(message: str) -> str:
    """
    Validate and sanitize commit message.
    
    Rules:
    - Max 200 characters
    - Strip HTML tags
    - No newlines
    
    Raises ValidationError if invalid.
    """
    if not message or not isinstance(message, str):
        raise ValidationError("commit_message is required and must be a string")
    
    # Remove HTML tags
    message = re.sub(r'<[^>]+>', '', message)
    
    # Remove newlines
    message = message.replace('\n', ' ').replace('\r', '')
    
    # Trim whitespace
    message = message.strip()
    
    if len(message) > MAX_COMMIT_MESSAGE_LENGTH:
        raise ValidationError(f"commit_message too long (max {MAX_COMMIT_MESSAGE_LENGTH} chars)")
    
    return message

def validate_project_name(project_name: str) -> str:
    """
    Validate project name and derive room code.
    
    Rules:
    - Convert to lowercase
    - Replace spaces with hyphens
    - Remove invalid characters
    - Max 50 characters
    
    Returns the sanitized room code.
    """
    if not project_name or not isinstance(project_name, str):
        raise ValidationError("project_name is required and must be a string")
    
    # Convert to lowercase
    room_code = project_name.lower()
    
    # Replace spaces and underscores with hyphens
    room_code = room_code.replace(' ', '-').replace('_', '-')
    
    # Remove invalid characters
    room_code = re.sub(r'[^a-z0-9-]', '', room_code)
    
    # Remove consecutive hyphens
    room_code = re.sub(r'-+', '-', room_code)
    
    # Remove leading/trailing hyphens
    room_code = room_code.strip('-')
    
    if not room_code:
        raise ValidationError("project_name results in empty room_code")
    
    if len(room_code) > MAX_ROOM_CODE_LENGTH:
        raise ValidationError(f"project_name too long (max {MAX_ROOM_CODE_LENGTH} chars)")
    
    return room_code

def require_admin_auth(f):
    """
    Decorator to require admin authentication.
    
    Expects API key in Authorization header:
    Authorization: Bearer <api_key>
    
    Or as query parameter:
    ?api_key=<api_key>
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Check Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            provided_key = auth_header[7:]
        else:
            # Check query parameter
            provided_key = request.args.get('api_key', '')
        
        if not provided_key:
            return jsonify({
                "error": "Authentication required",
                "message": "Provide API key in Authorization header or api_key parameter"
            }), 401
        
        if provided_key != ADMIN_API_KEY:
            return jsonify({
                "error": "Invalid API key",
                "message": "The provided API key is invalid"
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function

def validate_request_json(*required_fields):
    """
    Decorator to validate JSON request body.
    
    Usage:
        @validate_request_json('room_code', 'developer_id')
        def my_endpoint():
            data = request.get_json()
            ...
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({
                    "error": "Invalid content type",
                    "message": "Request must be application/json"
                }), 400
            
            data = request.get_json()
            if not data:
                return jsonify({
                    "error": "Invalid JSON",
                    "message": "Request body must be valid JSON"
                }), 400
            
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return jsonify({
                    "error": "Missing required fields",
                    "message": f"Required fields: {', '.join(missing_fields)}"
                }), 400
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator

def sanitize_html(text: str) -> str:
    """
    Remove HTML tags from text to prevent XSS.
    """
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', str(text))

def get_client_ip() -> str:
    """
    Get client IP address, respecting X-Forwarded-For header.
    """
    if request.headers.get('X-Forwarded-For'):
        # Get first IP from X-Forwarded-For chain
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'
