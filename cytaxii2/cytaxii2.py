import threading
import requests
import json
from datetime import datetime
import os
from typing import Optional, Dict, Any, Union
import logging

"""
Cyware TAXII 2.0/ 2.1 Client 
TAXII Supported Version: 2.0 & 2.1

The client caches the default API root after the first successful discovery.
Reuse the same client instance for multiple requests to avoid repeated discovery.
"""

# Cache API root by discovery_url so even new client instances avoid repeated discovery.
# Guarded by a lock for thread safety. Use clear_api_root_cache() to reset (e.g. in tests).
_api_root_cache = {}
_api_root_cache_lock = threading.Lock()


def clear_api_root_cache():
    """Clear the shared API root cache. Use when the server's default API root may have changed."""
    with _api_root_cache_lock:
        _api_root_cache.clear()


class cytaxii2(object):
    """
    TAXII 2.x client. Caches the API root after first discovery; reuse this
    instance for multiple requests to avoid repeated discovery calls.
    """

    def __init__(self, discovery_url, username, password, version=2.1, **kwargs):
        """
        This method is used to initialize values throughout the class
        :param discovery_url: Enter the TAXII 2.1 Discovery URL
        :param username: Enter the username to to authenticate with
        :param password: Enter the password to to authenticate with
        """
        if version == 2.1:
            self.headers = {
                'Content-Type': 'application/taxii+json;version=2.1',
                'User-Agent': 'cyware.taxii2client',
                'Accept': 'application/taxii+json;version=2.1'
            }
        elif version == 2.0:
            self.headers = {
                'Content-Type': 'application/vnd.oasis.stix+json; version=2.0',
                'User-Agent': 'cyware.httpclient',
                'Accept': 'application/vnd.oasis.taxii+json; version=2.0'
            }
        else:
            raise SyntaxError("Invalid version entered. Only TAXII versions 2.0 and 2.1 are supported")

        self.discovery_url = discovery_url
        self.api_root = None
        self.auth = (username, password)
        self.collections = "collections"
        self.objects = "objects"

    def request_handler(self, method, url, json_data=None, query_params=None, timeout=30, **kwargs):
        """
        Perform an HTTP request. Never raises. Returns status, status_code, response, headers.

        status_code is always set: HTTP code when a response was received (e.g. 429),
        or 500 when the request failed before any response.

        When response.ok is False, we still try to parse JSON; if the body is not
        valid JSON we do not raise—we return status_code and a clear message string
        (including the code), so 429 and other flux errors are visible.

        response: parsed JSON (dict/list) on success or when server returned JSON;
        otherwise a string (405 message, exception message, or parse error with status).

        headers: when an HTTP response was received, a dict of response header names
        to values (e.g. Retry-After, WWW-Authenticate, X-RateLimit-*); None when no
        response (e.g. connection error). Use for backoff, auth challenges, rate limits.

        timeout: passed to requests (default 30 seconds). Override via kwargs or this argument.
        **kwargs: forwarded to requests.get/post (e.g. timeout, verify).
        """
        if method not in ('GET', 'POST'):
            return {
                'status': False,
                'status_code': 405,
                'response': 'Unsupported Method requested',
                'headers': None,
            }

        req_kwargs = {'url': url, 'headers': self.headers, 'auth': self.auth, 'timeout': timeout, **kwargs}
        if method == 'GET':
            req_kwargs['params'] = query_params
            if json_data is not None:
                req_kwargs['data'] = json_data
        else:
            req_kwargs['params'] = query_params
            if isinstance(json_data, (dict, list)):
                req_kwargs['json'] = json_data
            elif json_data is not None:
                req_kwargs['data'] = json_data

        try:
            if method == 'GET':
                response = requests.get(**req_kwargs)
            else:
                response = requests.post(**req_kwargs)
        except requests.RequestException as e:
            return {
                'status': False,
                'status_code': 500,
                'response': str(e),
                'headers': None,
            }

        status_code = response.status_code
        body = response.text or ''
        response_headers = dict(response.headers)

        try:
            response_json = response.json() if body.strip() else None
        except (ValueError, TypeError) as e:
            raw_preview_len = 4096
            raw_preview = (body[:raw_preview_len] + '...') if len(body) > raw_preview_len else body
            err_msg = 'Invalid JSON: {} (HTTP {}). Raw response: {}'.format(
                e, status_code, raw_preview
            )
            return {
                'status': False,
                'status_code': status_code,
                'response': err_msg,
                'headers': response_headers,
            }

        status = True if response.ok else False
        if not response.ok and response_json is None:
            response_json = ""
        return {
            'status': status,
            'status_code': status_code,
            'response': response_json,
            'headers': response_headers,
        }

    def discovery_request(self, **kwargs):
        """
        This method is used to make a request to the TAXII discovery URL
        """
        response = self.request_handler(method='GET', url=self.discovery_url)
        return response

    def get_api_root(self, **kwargs):
        """
        Return the default API root for the TAXII server. The result is cached:
        - on this instance (self.api_root), and
        - by discovery_url (shared across instances for the same server),
        so discovery_request() is only called once per server. Reuse the same
        client instance when possible to avoid extra work.

        Returns
        :api_root (str): api root default if available, otherwise discover_request() response
        :early_return (bool): False if API root found, otherwise True (bad discover_request)
        """
        if self.api_root:
            return self.api_root, False
        with _api_root_cache_lock:
            if self.discovery_url in _api_root_cache:
                self.api_root = _api_root_cache[self.discovery_url]
                return self.api_root, False
        discover_response = self.discovery_request()
        resp = discover_response.get('response')
        if discover_response.get('status_code') == 200 and isinstance(resp, dict) and 'default' in resp:
            root = resp['default']
            if not isinstance(root, str) or not root.strip():
                return discover_response, True
            with _api_root_cache_lock:
                if self.discovery_url in _api_root_cache:
                    self.api_root = _api_root_cache[self.discovery_url]
                else:
                    _api_root_cache[self.discovery_url] = root
                    self.api_root = root
            return self.api_root, False
        return discover_response, True

    def root_discovery(self, **kwargs):
        """
        This method is used to make a root discovery request to the TAXII URL
        """
        api_root, early_return = self.get_api_root()
        if early_return:
            return api_root

        response = self.request_handler(method='GET', url=api_root)
        return response

    def collection_request(self, **kwargs):
        """
        This method is used to make a request to the TAXII server to get all collections on the server
        """
        api_root, early_return = self.get_api_root()
        if early_return:
            return api_root

        api_root = api_root.rstrip('/')
        collection_url = "{0}/{1}/".format(api_root, self.collections)
        response = self.request_handler(method='GET', url=collection_url)
        return response

    def collection_data_request(self, collection_id, **kwargs):
        """
        This method is used to get data about a particular collection on the TAXII server
        :param collection_id: Enter the collection ID
        """
        api_root, early_return = self.get_api_root()
        if early_return:
            return api_root

        api_root = api_root.rstrip('/')
        poll_url = "{0}/{1}/{2}/".format(api_root, self.collections, collection_id)
        response = self.request_handler(method='GET', url=poll_url)
        return response

    def poll_request(self, collection_id, added_after=None, limit=None, object_id=None, next=None, object_type=None,
                     **kwargs):
        """
        This method is used to poll data from a particular collection
        :param object_type: Enter the indicator type to retrieve
        :param next: Enter the next integer if the data has been paginated
        :param object_id: Enter a specific object to retrieve
        :param limit: Enter response limit
        :param added_after: Enter the date to poll from, polls all data if left blank
        :param collection_id: Enter the collection ID
        """
        api_root, early_return = self.get_api_root()
        if early_return:
            return api_root

        params = {
            'added_after': added_after,
            'limit': limit,
            'next': next,
            'match[id]': object_id,
            'match[type]': object_type
        }
        api_root = api_root.rstrip('/')
        poll_url = "{0}/{1}/{2}/{3}/".format(api_root, self.collections, collection_id, self.objects)
        response = self.request_handler(method='GET', url=poll_url, query_params=params)
        return response

    def inbox_request(self, collection_id, stix_bundle, **kwargs):
        """
        This method is used to make an inbox request to the TAXII server.
        :param collection_id: Enter the collection ID
        :param stix_bundle: STIX data to make an inbox request to
        """
        api_root, early_return = self.get_api_root()
        if early_return:
            return api_root

        api_root = api_root.rstrip('/')
        inbox_url = "{0}/{1}/{2}/{3}/".format(api_root, self.collections, collection_id, self.objects)
        response = self.request_handler(method='POST', url=inbox_url, json_data=stix_bundle)
        return response

    def download_indicator(self, collection_id: str, object_id: str, filename: Optional[str] = None) -> bool:
        """
        Downloads a specific indicator as a TXT file.
        
        Args:
            collection_id (str): The collection ID containing the indicator
            object_id (str): The specific object ID to download
            filename (str, optional): Custom filename for the downloaded indicator.
                                   If not provided, generates filename using timestamp,
                                   object_id, and collection_id
        
        Returns:
            bool: True if download was successful, False otherwise
        
        Raises:
            ValueError: If collection_id or object_id is empty
        """
        # Input validation
        if not collection_id or not collection_id.strip():
            raise ValueError("collection_id cannot be empty")
        if not object_id or not object_id.strip():
            raise ValueError("object_id cannot be empty")

        try:
            # Fetch the indicator
            response = self.poll_request(collection_id=collection_id, object_id=object_id)
            
            if not response['status']:
                logging.error(f"Failed to fetch indicator: {response.get('response', 'Unknown error')}")
                return False
            
            # Validate response data
            if not response.get('response'):
                logging.error("No data received in response")
                return False

            # Handle empty objects array in response
            response_data = response['response']
            if isinstance(response_data, dict) and 'objects' in response_data:
                if not response_data['objects']:
                    logging.error(f"No indicator found with ID {object_id}")
                    return False
                response_data = response_data['objects'][0]  # Take first object if multiple returned
            
            # Generate default filename if none provided
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_collection_id = "".join(c if c.isalnum() else "_" for c in collection_id)
                safe_object_id = "".join(c if c.isalnum() else "_" for c in object_id)
                filename = f"indicator_{timestamp}_{safe_collection_id}_{safe_object_id}.txt"
            elif not filename.endswith('.txt'):
                filename = f"{filename}.txt"
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
            
            # Write the indicator data to file
            with open(filename, 'w') as f:
                json.dump(response_data, f, indent=2)
            
            logging.info(f"Successfully downloaded indicator to {filename}")
            return True
            
        except Exception as e:
            logging.error(f"Error downloading indicator: {str(e)}")
            return False
