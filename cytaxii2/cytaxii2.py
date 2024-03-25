import requests

"""
Cyware TAXII 2.0/ 2.1 Client 
TAXII Supported Version: 2.0 & 2.1
"""


class cytaxii2(object):
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

    def request_handler(self, method, url, json_data=None, query_params=None, **kwargs):
        """
        This method is used to handle all TAXII requests
        :param query_params: Any query params to pass
        :param method: Enter the HTTP method to use
        :param url: Enter the URL to make the request to
        :param json_data: Enter the json data to pass as a payload
        """
        try:
            if method == 'GET':
                response = requests.get(url=url, data=json_data, headers=self.headers, auth=self.auth,
                                        params=query_params)
            elif method == 'POST':
                response = requests.post(url=url, data=json_data, headers=self.headers, auth=self.auth,
                                         params=query_params)
            else:
                return {
                    'response': 'Unsupported Method requested',
                    'status': False,
                    'status_code': 405
                }

            status_code = response.status_code

            if response.ok:
                response_json = response.json()
                status = True
            else:
                response_json = response.json()
                status = False

        except Exception as e:
            status_code = 'EXCEPTION'
            response_json = str(e)
            status = False

        return {
            'response': response_json,
            'status': status,
            'status_code': status_code
        }

    def discovery_request(self, **kwargs):
        """
        This method is used to make a request to the TAXII discovery URL
        """
        response = self.request_handler(method='GET', url=self.discovery_url)
        return response

    def get_api_root(self, **kwargs):
        """
        This method is used to manage retreiving the default API root for TAXII server.

        Returns
        :api_root (str): api root default if available, otherwise discover_request() response
        :early_return (bool): False if API root found, otherwise True (bad discover_request)
        """
        if not self.api_root:
            discover_response = self.discovery_request()
            if discover_response['status_code'] == 200:
                self.api_root = discover_response['response']['default']
            else:
                return discover_response, True

        return self.api_root, False

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
